import requests
import json
import os

API_URL = "https://localhost:3443/api/import/screenshot"
LOGIN_URL = "https://localhost:3443/api/auth/login"

import sys

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def login_to_backend(username, password):
    try:
        response = requests.post(LOGIN_URL, json={"username": username, "password": password}, verify=False)
        if response.status_code == 200:
            return response.json().get("token"), None
        else:
            return None, response.json().get("error", "로그인 실패")
    except Exception as e:
        return None, f"서버 연결 오류: {e}"

def upload_to_backend(data, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, json=data, headers=headers, verify=False)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"업로드 실패 (상태 코드 {response.status_code}): {response.text}"
    except Exception as e:
        return False, f"백엔드 통신 오류: {e}"
