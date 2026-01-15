import os
from openai import OpenAI


api_key = "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"
def main():
    client = OpenAI(
        api_key=api_key,
    )
    response = client.chat.completions.create(
        model="gpt-4o",  # 或其他你想用的模型
        messages=[
            {"role": "system", "content": "你是一个乐于助人的中文助手。"},
            {"role": "user", "content": "帮我用一两句话介绍一下 OpenAI 的 API。"},
        ],
    )
    print(response.choices[0].message.content)  


if __name__ == '__main__':
    main()