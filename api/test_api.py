import requests
import json


class TestAPI:
    def test_upload(self):
        url = "http://localhost:8080/api/v1.0/posts"\
            "/upload?tags=test_image+test_tag+highres&rating=safe"
        with open("api/wl-logo.png", "rb") as f:
            image = f.read()
        payload = image
        headers = {
            'Content-Type': 'image/jpeg'
        }
        response = requests.request("POST", url, headers=headers,
                                    data=payload)
        data = json.loads(response.text)
        assert data['height'] == 512
        assert data['md5_hash'] == "43e4986442fc97d495e9759fdadc4231"
        assert data['rating'] == "safe"
        assert data['tags'] == ["test_image", "test_tag", "highres"]
        assert data['width'] == 512

    def test_get_image(self):
        url = "http://localhost:8080/api/v1.0/images/1"
        response = requests.request("GET", url)
        assert response.status_code == 200

    def test_delete_image(self):
        url = "http://localhost:8080/api/v1.0/posts/delete/1"
        response = requests.request("DELETE", url)
        assert response.text == "Image deleted"
