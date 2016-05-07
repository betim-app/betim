from datetime import datetime
import json

from flask import Flask, Response, request
from pymongo import MongoClient
from bson import json_util
from clarifai.client import ClarifaiApi
import urbanairship as ua
from urbanairship import ios

from settings_local import (
    CLARIFAI_APP_ID, CLARIFAI_APP_SECRET,
    UA_KEY, UA_SECRET
)

app = Flask(__name__)
db = MongoClient()["betim"]

airship = ua.Airship(UA_KEY, UA_SECRET)

clarifai_api = ClarifaiApi(
    app_id=CLARIFAI_APP_ID,
    app_secret=CLARIFAI_APP_SECRET
)


def jsonify(data):
    return Response(json_util.dumps(data),
                    mimetype='application/json')


@app.route("/images", methods=['GET'])
def get_images():
    result = db.images.find({
        "comment": None
    }).sort([
        ['date_creation', -1]
    ])

    return jsonify({
        'images': [
            {
                'id': str(image.get('_id')),
                'description': image.get('description'),
                'url': image.get('url'),
                'comment': image.get('comment'),
                'date_creation': image.get('date_creation').isoformat()
            } for image in result
            ]
    })


def get_tags(url):
    response = clarifai_api.tag_image_urls(url)
    results = response['results']

    if not results:
        return

    matched = results[0]

    return matched['result']['tag']['classes']


def send_push_notification():
    push = airship.create_push()
    push.audience = ua.all_
    push.notification = ua.notification(
        alert="Betimlenecek bir gorsel var",
        ios=ios(sound='betim', badge=1),
    )
    push.device_types = ua.all_
    push.send()


@app.route("/images", methods=['POST'])
def post_images():
    data = request.json
    url = data.get('url')

    matched = db.images.find_one({
        "url": url
    })

    if matched:
        return jsonify({
            'id': str(matched.get('_id')),
            'description': matched.get('description'),
            'comment': matched.get('comment') or 'Just asked.'
        })

    tags = get_tags(url)
    description = ' '.join(tags)

    inserted = db.images.insert({
        "url": url,
        "description": description,
        'date_creation': datetime.now()
    })

    response = jsonify({
        'id': str(inserted),
        'description': description,
        'comment': 'Just asked.'
    })

    send_push_notification()

    response.status_code = 201
    return response


@app.route("/images", methods=['PUT'])
def update_image():
    data = request.json
    url = data.get('url')
    comment = data.get('comment')

    inserted = db.images.update_one({
        "url": url
    }, {
        "$set": {
            "comment": comment
        }
    })

    response = jsonify({
        'success': True
    })

    response.status_code = 202
    return response


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response


if __name__ == "__main__":
    send_push_notification()#app.run(host="0.0.0.0", port=8080, debug=True)

