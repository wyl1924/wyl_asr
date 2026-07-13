#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests

def verify_meeting_27():
    try:
        response = requests.get('http://localhost:8080/api/meetings/documents/list?meeting_id=27')
        print(f'状态码: {response.status_code}')
        
        if response.status_code == 200:
            result = response.json()
            print(f'文档数量: {result["data"]["total"]}')
            
            if result['data']['documents']:
                print('\n文档列表:')
                for doc in result['data']['documents']:
                    print(f'  - {doc["filename"]} (类型: {doc["type"]}, 大小: {doc["file_size"]} 字节)')
                    print(f'    下载URL: {doc["download_url"]}')
            else:
                print('没有找到文档')
        else:
            print(f'请求失败: {response.text}')
            
    except Exception as e:
        print(f'请求异常: {e}')

if __name__ == '__main__':
    verify_meeting_27()