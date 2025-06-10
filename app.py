import os
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
try:
    import google.generativeai as genai
except Exception:
    genai = None

app = Flask(__name__)

# In-memory chat data
chat_state = {
    'user_personality': '',
    'characters': [],  # list of {'name': str, 'description': str}
    'provider': 'openai',
    'api_key': '',
    'model': '',
    'messages': [],  # list of {'role': 'user'|'assistant', 'content': str}
    'summary': ''
}

# Helpers
def provider_completion(prompt, messages, provider, api_key, model):
    if provider == 'openai':
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=messages
        )
        return resp.choices[0].message.content

    elif provider == 'gemini' and genai:
        genai.configure(api_key=api_key)
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(messages)
        return response.text
    else:
        raise ValueError('Unknown provider or missing library')


def summarize_history(provider, api_key, model, messages):
    summary_prompt = 'Summarize the following chat briefly so the AI can remember the context.'
    summary_messages = [{'role': 'system', 'content': summary_prompt}] + messages
    try:
        return provider_completion(summary_prompt, summary_messages, provider, api_key, model)
    except Exception as e:
        print('Summary failed', e)
        return ''


    system_prompt = f"Ты участвуешь в ролевом чате. Личность пользователя: {chat_state['user_personality']}\n"
        system_prompt += f"Персонаж {c['name']}: {c['description']}\n"
        system_prompt += f"Краткое содержание прошлых сообщений:\n{chat_state['summary']}\n"
    system_prompt += (
        "Все персонажи общаются и действуют как настоящие люди. "
        "Опиши их действия и эмоции вместе с репликой."
    )
@app.route('/create_chat', methods=['POST'])
def create_chat():
    chat_state['user_personality'] = request.form.get('personality', '')
    chat_state['characters'] = []
    character_names = request.form.getlist('character_name')
    character_descs = request.form.getlist('character_desc')
    for n, d in zip(character_names, character_descs):
        if n.strip() and d.strip():
            chat_state['characters'].append({'name': n.strip(), 'description': d.strip()})
    chat_state['provider'] = request.form.get('provider')
    chat_state['api_key'] = request.form.get('api_key')
    chat_state['model'] = request.form.get('model')
    chat_state['messages'] = []
    chat_state['summary'] = ''
    return ('', 204)

@app.route('/send_message', methods=['POST'])
def send_message():
    user_msg = request.form.get('message')
    chat_state['messages'].append({'role': 'user', 'content': user_msg})

    system_prompt = f"You are in a roleplay chat. The user personality is: {chat_state['user_personality']}\n"
    for c in chat_state['characters']:
        system_prompt += f"Character {c['name']}: {c['description']}\n"
    if chat_state['summary']:
        system_prompt += f"Past summary:\n{chat_state['summary']}\n"
    system_prompt += 'All characters should talk like real people.'

    messages = [{'role': 'system', 'content': system_prompt}] + chat_state['messages']
    try:
        ai_reply = provider_completion(system_prompt, messages, chat_state['provider'], chat_state['api_key'], chat_state['model'])
    except Exception as e:
        ai_reply = f"Error from provider: {e}"

    chat_state['messages'].append({'role': 'assistant', 'content': ai_reply})

    if len(chat_state['messages']) >= 20 and len(chat_state['messages']) % 10 == 0:
        # summarizing every 10 user+assistant pairs
        chat_state['summary'] += '\n' + summarize_history(
            chat_state['provider'], chat_state['api_key'], chat_state['model'], chat_state['messages'][-20:])
    return jsonify({'reply': ai_reply})

@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    chat_state['messages'] = []
    chat_state['summary'] = ''
    return ('', 204)

if __name__ == '__main__':
    app.run(debug=True)
