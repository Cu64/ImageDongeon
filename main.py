#!/usr/bin/env python3
import re
import cv2
import time
import json
import hashlib
import requests
import numpy as np
import credentials
from PIL import Image
import pymysql.cursors
from io import BytesIO
from flask_cors import CORS
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
# TODO: Fucking remove CORS from literally fucking everywhere.
CORS(app)


@app.route('/api/v1.0/posts/upload', methods=['POST'])
def upload_post():
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
    print(type(image))
    print(str(image)[0:10])
    post['tags'] = tags.split(" ")
    for tag in post['tags']:
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
            sql = "INSERT INTO posts(md5_hash, post_time, height, width, "\
                  "rating, image) VALUES (%s, %s, %s, %s, %s, %s);"
            values = (post['md5_hash'], post['post_time'], post['height'],
                      post['width'], post['rating'], image)
            cursor.execute(sql, values)
            cursor.execute("SET @post_id = LAST_INSERT_ID();")
            for tag in post['tags']:
                sql = "SELECT * FROM tags WHERE name='{}' LIMIT 1;"
                cursor.execute(sql.format(tag))
                exist = cursor.fetchone()
                if exist is None:
                    sql = "INSERT INTO tags (name) VALUES ('{}')".format(tag)
                    cursor.execute(sql)
                    cursor.execute("SET @tag_id = LAST_INSERT_ID();")
                else:
                    sql = "SELECT @tag_id := tag_id FROM tags WHERE name='{}';"
                    cursor.execute(sql.format(tag))
                sql = "INSERT INTO post_tag_map (post_id, tag_id)"\
                      " VALUES(@post_id, @tag_id);"
                cursor.execute(sql)
        connection.commit()
    finally:
        connection.close()
    return jsonify(post)


@app.route('/api/v1.0/images/<int:id>', methods=['GET'])
def get_image(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT image FROM posts WHERE post_id=%s"
            cursor.execute(sql, (id))
            image = cursor.fetchone()['image']
            im = Image.open(BytesIO(image))
            try:
                return Response(image, mimetype=Image.MIME[im.format])
            except TypeError:
                return "Image is not found in DB/is deleted."
    finally:
        connection.close()


@app.route('/api/v1.0/thumbs/<int:id>', methods=['GET'])
def get_thumb(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM thumbnails WHERE thumb_id='{}' LIMIT 1;"
            cursor.execute(sql.format(id))
            result = cursor.fetchone()
            if result is None:
                sql = "SELECT * FROM posts WHERE post_id='{}'"
                cursor.execute(sql.format(id))
                image = cursor.fetchone()['image']
                im = Image.open(BytesIO(image))
                basewidth = 300
                wpercent = (basewidth/float(im.size[0]))
                hsize = int((float(im.size[1])*float(wpercent)))
                thumbnail = im.resize((basewidth, hsize), Image.ANTIALIAS)
                temp = BytesIO()
                thumbnail.save(temp, format="png", quality='web_maximum')
                sql = "INSERT INTO thumbnails(thumb_id, image) VALUES (%s, %s)"
                values = (id, temp.getvalue())
                cursor.execute(sql, values)
                connection.commit()
                return Response(temp.getvalue(), mimetype='image/png')
            else:
                return Response(result['image'], mimetype='image/png')
    finally:
        connection.close()


@app.route('/api/v1.0/thumbs/deleteall', methods=['DELETE'])
def delete_all_thumbnails():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE thumbnails")
        return jsonify(success=True)
    finally:
        connection.close()


@app.route('/api/v1.0/posts/delete/<int:id>', methods=['DELETE'])
def delete_post(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            queries = [
                "DELETE FROM post_tag_map WHERE post_id=%s",
                "DELETE FROM posts WHERE post_id=%s"
            ]
            for query in queries:
                cursor.execute(query, (id))
            connection.commit()
        return jsonify(success=True)
    finally:
        connection.close()


@app.route('/api/v1.0/posts/search', methods=['GET'])
def search_post_by_tags():
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
                tag_query.append("'{0}'".format(tag))
            sql = "SELECT p.post_id, p.md5_hash, p.post_time, p.height, "\
                  "p.width, p.rating FROM post_tag_map pt, posts p, tags t "\
                  "WHERE pt.tag_id = t.tag_id AND (t.name IN ({})) AND "\
                  "p.post_id = pt.post_id GROUP BY p.post_id HAVING "\
                  "COUNT( p.post_id )={};"
            cursor.execute(sql.format(", ".join(tag_query), len(tag_query)))
            posts = cursor.fetchall()
            sql = "SELECT post_id, name FROM post_tag_map INNER JOIN tags "\
                  "ON (post_tag_map.tag_id=tags.tag_id) WHERE post_id IN ({})"
            post_ids = []
            for post in posts:
                post_ids.append(str(post["post_id"]))
            try:
                cursor.execute(sql.format(", ".join(post_ids)))
            except pymysql.err.ProgrammingError:
                return "false"
            result = cursor.fetchall()
            for post in posts:
                post['tags'] = []
            for tag in result:
                for post in posts:
                    if post['post_id'] == tag['post_id']:
                        posts[posts.index(post)]['tags'].append(tag['name'])
    finally:
        connection.close()
    return jsonify(posts)


@app.route('/api/v1.0/posts/<int:id>', methods=['GET'])
def search_post_by_id(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT post_id, md5_hash, post_time, height, "\
                  "width, rating FROM posts WHERE post_id=%s"
            cursor.execute(sql, (id))
            post = cursor.fetchone()
            sql = "SELECT post_id, name FROM post_tag_map INNER JOIN "\
                  "tags ON (post_tag_map.tag_id = tags.tag_id) "\
                  "WHERE post_id IN ({})"
            cursor.execute(sql.format(id))
            result = cursor.fetchall()
            post["tags"] = []
            for tag in result:
                post["tags"].append(tag['name'])
    finally:
        connection.close()
    return jsonify(post)


@app.route('/api/v1.0/posts/deleteall', methods=['DELETE'])
def delete_all_posts():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            queries = [
                "SET FOREIGN_KEY_CHECKS = 0",
                "TRUNCATE post_tag_map",
                "TRUNCATE posts",
                "TRUNCATE tags",
                "SET FOREIGN_KEY_CHECKS = 1"
            ]
            for query in queries:
                cursor.execute(query)
            return jsonify(success=True)
    finally:
        connection.close()


@app.route('/api/v1.0/posts/all', methods=['GET'])
def get_all_posts():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "SELECT post_id, md5_hash, post_time, "\
                  "height, width, rating FROM posts"
            cursor.execute(sql)
            posts = cursor.fetchall()
            for post in posts:
                post["tags"] = []
            sql = "SELECT post_id, name FROM post_tag_map INNER JOIN tags "\
                  "ON (post_tag_map.tag_id=tags.tag_id) WHERE post_id IN ({})"
            post_ids = []
            for post in posts:
                post_ids.append(str(post["post_id"]))
            cursor.execute(sql.format(", ".join(post_ids)))
            result = cursor.fetchall()
            for post in posts:
                post['tags'] = []
            for tag in result:
                posts[tag['post_id'] - 1]['tags'].append(tag['name'])
    finally:
        connection.close()
    return jsonify(posts)


@app.route('/api/v1.0/settings/reset', methods=['DELETE'])
def reset_settings():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            queries = [
                "TRUNCATE settings",
                "INSERT INTO settings"
                "(`key`, `value`) VALUES ('featured_post', '0')"
            ]
            for query in queries:
                cursor.execute(query)
                connection.commit()
            return jsonify(success=True)
    finally:
        connection.close()


@app.route('/api/v1.0/settings/featured_post', methods=['GET'])
def get_featured_post():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM settings"
                           " WHERE `key`='featured_post'")
            featured_post = cursor.fetchone()
    finally:
        connection.close()
    if int(featured_post["value"]) == 0:
        return jsonify(featured_post=False)
    else:
        return jsonify(featured_post=int(featured_post["value"]))


@app.route('/api/v1.0/settings/feature_post/<int:id>', methods=['POST'])
def feature_post(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE settings SET `value` = '%s' "\
                  "WHERE `key` = 'featured_post'"
            cursor.execute(sql, (id))
            connection.commit()
        return jsonify(featured_post=id)
    finally:
        connection.close()


@app.route('/api/v1.0/tags/<string:name>', methods=['GET'])
def get_tag(name):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tags WHERE name='{}'".format(name))
            tags = cursor.fetchone()
    finally:
        connection.close()
    return jsonify(tags)


@app.route('/api/v1.0/tags/setdesc/<string:name>', methods=['POST'])
def set_description(name):
    description = request.args.get('description')
    description = re.sub('[^a-zA-Z_ ]', '', description)
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE tags SET description='{}' WHERE name='{}'"
            cursor.execute(sql.format(description, name))
            connection.commit()
            return jsonify(success=True)
    finally:
        connection.close()
    return jsonify()


@app.route('/api/v1.0/tags/all', methods=['GET'])
def get_all_tags():
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM tags")
            tags = cursor.fetchall()
            tag_names = []
            for tag in tags:
                tag_names.append(tag['name'])
    finally:
        connection.close()
    return jsonify(tags=tag_names)


@app.route('/api/v1.0/import/gelbooru/<int:id>', methods=['POST'])
def import_gelbooru(id):
    connection = pymysql.connect(
        host=credentials.host,
        user=credentials.user,
        password=credentials.password,
        db=credentials.db,
        cursorclass=pymysql.cursors.DictCursor
    )
    url = "https://gelbooru.com/index.php?page="\
          "dapi&s=post&q=index&json=1&id={}"
    url = url.format(id)
    response = requests.get(url)
    data = json.loads(response.text)[0]
    post = {}
    post['md5_hash'] = data['hash']
    post['post_time'] = int(time.time())
    post['height'] = data['height']
    post['width'] = data['width']
    if data['rating'] == 'e':
        post['rating'] = "explicit"
    elif data['rating'] == 'q':
        post['rating'] = "questionable"
    elif data['rating'] == 's':
        post['rating'] = "safe"
    post['tags'] = data['tags'].split(" ")
    image_url = data['file_url']
    response = requests.get(image_url)
    image = response.content
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO posts(md5_hash, post_time, height, width, "\
                      "rating, image) VALUES (%s, %s, %s, %s, %s, %s);"
            values = (post['md5_hash'], post['post_time'], post['height'],
                      post['width'], post['rating'], image)
            cursor.execute(sql, values)
            cursor.execute("SET @post_id = LAST_INSERT_ID();")
            for tag in post['tags']:
                sql = "SELECT * FROM tags WHERE name='{}' LIMIT 1;"
                cursor.execute(sql.format(tag))
                exist = cursor.fetchone()
                if exist is None:
                    sql = "INSERT INTO tags (name) VALUES ('{}')".format(tag)
                    cursor.execute(sql)
                    cursor.execute("SET @tag_id = LAST_INSERT_ID();")
                else:
                    sql = "SELECT @tag_id := tag_id FROM tags WHERE name='{}';"
                    cursor.execute(sql.format(tag))
                sql = "INSERT INTO post_tag_map (post_id, tag_id)"\
                      " VALUES(@post_id, @tag_id);"
                cursor.execute(sql)
        connection.commit()
    finally:
        connection.close()
    return jsonify(post)


if __name__ == "__main__":
    app.run(port=8080)
