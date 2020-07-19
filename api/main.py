#!/usr/bin/env python3
import cv2
import time
import hashlib
import numpy as np
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/api/v1.0')
def index():
    return "Welcome to Image Dongeon's API."


@app.route('/api/v1.0/posts/upload')
def uploadPost():
    post = {}
    tags = request.args.get('tags')
    post['rating'] = request.args.get('rating')
    image = request.get_data()
    post['tags'] = tags.split(" ")
    post['md5_hash'] = hashlib.md5(image).digest().hex()
    post['post_time'] = int(time.time())
    try:
        post['height'], post['width'], _ = cv2.imdecode(
            np.frombuffer(image, dtype=np.uint8),
            cv2.IMREAD_UNCHANGED).shape
    except cv2.error:
        return "No image attached"
    return jsonify(post)


if __name__ == "__main__":
    app.run(port=8080, debug=True)
