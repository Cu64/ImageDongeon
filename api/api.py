#!/usr/bin/env python3
import cv2
import time
import magic
import hashlib
import numpy as np
import pymysql.cursors
from flask import Flask, jsonify, request, Response

app = Flask(__name__)


@app.route('/api/v1.0', methods=['GET'])
def index():
    return "Welcome to Image Dongeon's API."


@app.route('/api/v1.0/posts/upload', methods=['POST'])
def uploadPost():
    connection = pymysql.connect(
        host='localhost',
        user='dongeonguard',
        password='SuchWow',
        db='imagedongeon',
        cursorclass=pymysql.cursors.DictCursor
    )
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
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO imagedongeon(md5_hash, tags, post_time, height, width,\
                 rating, image) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            values = (post['md5_hash'], " ".join(post['tags']),
                      post['post_time'], post['height'], post['width'],
                      post['rating'], image)
            cursor.execute(sql, values)
        connection.commit()
    finally:
        connection.close()
    return jsonify(post)


@app.route('/api/v1.0/images/<id>', methods=['GET'])
def getImage(id):
    connection = pymysql.connect(
        host='localhost',
        user='dongeonguard',
        password='SuchWow',
        db='imagedongeon',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT image FROM imagedongeon WHERE id=%s"
            cursor.execute(sql, (id))
            image = cursor.fetchone()
            try:
                return Response(image['image'],
                                mimetype=magic.from_buffer(image['image'],
                                mime=True))
            except TypeError:
                return "Image is not found in DB/is deleted."
    finally:
        connection.close()


@app.route('/api/v1.0/posts/delete/<id>', methods=['DELETE'])
def deletePost(id):
    connection = pymysql.connect(
        host='localhost',
        user='dongeonguard',
        password='SuchWow',
        db='imagedongeon',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "DELETE FROM imagedongeon WHERE id=%s"
            cursor.execute(sql, (id))
            connection.commit()
    finally:
        connection.close()
        return "Image deleted"


if __name__ == "__main__":
    app.run(port=8080, debug=True)
