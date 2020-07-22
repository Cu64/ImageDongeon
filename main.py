#!/usr/bin/env python3
import re
import cv2
import time
import magic
import hashlib
import numpy as np
import credentials
import pymysql.cursors
from datetime import datetime
from flask import Flask, jsonify, request, Response, render_template

app = Flask(__name__)


@app.route('/api/v1.0/posts/upload', methods=['POST'])
def uploadPost():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    post = {}
    tags = request.args.get('tags')
    post['rating'] = request.args.get('rating')
    image = request.get_data()
    post['tags'] = tags.split(" ")
    for tag in tags:
        tag = re.sub('[^a-zA-Z_]', '', tag)
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


@app.route('/api/v1.0/images/<int:id>', methods=['GET'])
def getImage(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
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


@app.route('/api/v1.0/posts/delete/<int:id>', methods=['DELETE'])
def deletePost(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "DELETE FROM imagedongeon WHERE id=%s"
            cursor.execute(sql, (id))
            connection.commit()
        return "Image deleted"
    finally:
        connection.close()


@app.route('/api/v1.0/posts/search', methods=['GET'])
def searchPostByTags():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    tags = request.args.get('tags')
    for tag in tags:
        tag = re.sub('[^a-zA-Z_]', '', tag)
    try:
        with connection.cursor() as cursor:
            tag_query = []
            for tag in tags.split(" "):
                tag_query.append("tags LIKE '%{0}%'".format(tag))
            sql = "SELECT id, md5_hash, tags, post_time, height, width, rating FROM imagedongeon WHERE {0}".format(" AND ".join(tag_query))
            cursor.execute(sql)
            posts = cursor.fetchall()
            for post in posts:
                post["tags"] = post["tags"].split(" ")
    finally:
        connection.close()
    return jsonify(posts)


@app.route('/api/v1.0/posts/<int:id>', methods=['GET'])
def searchPostByID(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id, md5_hash, tags, post_time, height, "\
                  "width, rating FROM imagedongeon WHERE id=%s"
            cursor.execute(sql, (id))
            post = cursor.fetchone()
            post["tags"] = post["tags"].split(" ")
    finally:
        connection.close()
    return jsonify(post)


@app.route('/api/v1.0/posts/deleteall', methods=['DELETE'])
def deleteAllPosts():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "TRUNCATE imagedongeon"
            cursor.execute(sql)
            return "Wiped Database"
    finally:
        connection.close()


@app.route('/api/v1.0/posts/all', methods=['GET'])
def getAllPosts():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id, md5_hash, tags, post_time, "\
                  "height, width, rating FROM imagedongeon"
            cursor.execute(sql)
            posts = cursor.fetchall()
            for post in posts:
                post["tags"] = post["tags"].split(" ")
    finally:
        connection.close()
    return jsonify(posts)


@app.route('/posts/<int:id>')
def viewPost(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT id, md5_hash, tags, post_time, height, "\
                  "width, rating FROM imagedongeon WHERE id=%s"
            cursor.execute(sql, (id))
            post = cursor.fetchone()
            post["tags"] = post["tags"].split(" ")
            post["post_time"] = datetime.fromtimestamp(post["post_time"]).strftime("%Y-%m-%d %H:%M:%S")
            return render_template("posts.html.jinja", post=post)
    finally:
        connection.close()


if __name__ == "__main__":
    app.run(port=8080)
