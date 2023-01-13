import requests
import vk_api.utils
import vk_api
from pony.orm import db_session
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import logging

import handlers
from models import UserState, Registration

try:
    from config import TOKEN, MY_GROUP, SCENARIOS, INTENTS, DEFAULT_ANSWER, FLIGHTS, DEFAULT_ANSWER_WITH_USER_NAME
except ImportError:
    TOKEN, MY_GROUP, SCENARIOS, INTENTS, DEFAULT_ANSWER, FLIGHTS = None, None, None, None, None, None
    print('cp config.py.default config.py and set token')
    exit()

log = logging.getLogger('bot')


def configure_logging():
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    stream_handler.setLevel(logging.INFO)
    log.addHandler(stream_handler)
    file_handler = logging.FileHandler('bot.log', encoding='utf8')
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                                datefmt='%d-%m-%Y %H:%M'))
    file_handler.setLevel(logging.DEBUG)
    log.addHandler(file_handler)
    log.setLevel(logging.DEBUG)


class Bot:
    """
    Echo bot для vk.com

    Use python3.7
    """
    def __init__(self, group_id, token):
        """
        :param group_id: group id группы vk
        :param token: секретный токен
        """
        self.group_id = group_id
        self.token = token
        self.vk = vk_api.VkApi(token=token)
        self.long_poll = VkBotLongPoll(self.vk, self.group_id)
        self.api = self.vk.get_api()

    def run(self):
        """Запуск бота."""
        for event in self.long_poll.listen():
            try:
                self.on_event(event)
            except Exception:
                log.exception('Ошибка в обработке события')

    @db_session
    def on_event(self, event):
        """Отправляет сообщение назад, если это текст.
        :param event: VkBotMessageEvent
        """
        if event.type != VkBotEventType.MESSAGE_NEW:
            log.info('неизвестный нам тип события %s', event.type)
            return
        user_id = event.object.peer_id
        text = event.object.text

        state = UserState.get(user_id=str(user_id))
        if state is not None:
            for intent in INTENTS:
                if any(token in text for token in intent['tokens']):
                    state.delete()
                    if intent['answer']:
                        self.send_text(intent['answer'], user_id)
                    else:
                        self.start_scenario(user_id, intent['scenario'], text)
                    break
            else:
                self.continue_scenario(text, state, user_id)
        else:
            for intent in INTENTS:
                if any(token in text for token in intent['tokens']):
                    if intent['answer']:
                        self.send_text(intent['answer'], user_id)
                    else:
                        self.start_scenario(user_id, intent['scenario'], text)
                    break
            else:
                # text_to_send = DEFAULT_ANSWER_WITH_USER_NAME.format(
                #     user_name=self.api.users.get(user_ids=user_id)[0]['first_name'])
                text_to_send = DEFAULT_ANSWER
                self.send_text(text_to_send, user_id)

    def send_text(self, text_to_send, user_id):
        self.api.messages.send(message=text_to_send, random_id=vk_api.utils.get_random_id(),
                               peer_id=user_id)

    def send_image(self, image, user_id):
        upload_url = self.api.photos.getMessagesUploadServer()['upload_url']
        upload_data = requests.post(url=upload_url, files={'photo': ('image.png', image, 'image/png')}).json()
        image_data = self.api.photos.saveMessagesPhoto(**upload_data)
        owner_id = image_data[0]['owner_id']
        media_id = image_data[0]['id']
        attachment = f'photo{owner_id}_{media_id}'
        self.api.messages.send(attachment=attachment, random_id=vk_api.utils.get_random_id(),
                               peer_id=user_id)

    def send_step(self, step, user_id, text, context):
        if 'text' in step:
            self.send_text(step['text'].format(**context), user_id)
        if 'image' in step:
            handler = getattr(handlers, step['image'])
            image = handler(context)
            self.send_image(image, user_id)

    def start_scenario(self, user_id, scenario_name, text):
        scenario = SCENARIOS[scenario_name]
        first_step = scenario['first_step']
        step = scenario['steps'][first_step]
        self.send_step(step, user_id, text, context={})
        UserState(user_id=str(user_id), scenario_name=scenario_name, step_name=first_step, context={})
        context_update = UserState.get(user_id=str(user_id))
        context_update.context['cities'] = '\n'.join(FLIGHTS.keys())
        context_update.context['user_name'] = self.api.users.get(user_ids=user_id)[0]['first_name']
        context_update.context['user_id'] = str(user_id)

    def continue_scenario(self, text, state, user_id):
        steps = SCENARIOS[state.scenario_name]['steps']
        step = steps[state.step_name]
        handler = getattr(handlers, step['handler'])
        if handler(text=text, context=state.context) == 1:
            # next step
            next_step = steps[step['next_step']]
            self.send_step(next_step, user_id, text, state.context)
            if next_step['next_step']:
                # switch to next step
                state.step_name = step['next_step']
            else:
                # finish scenario
                log.info('Зарегистрирован: {user_name} {flight}'.format(**state.context))
                Registration(user_id=state.context['user_id'], phone_number=state.context['phone_number'],
                             flight=state.context['flight'], sits_count=state.context['sits'],
                             comment=state.context['comment'], arrival_city=state.context['arrival'],
                             departure_city=state.context['departure'], email=state.context['email'])
                state.delete()
        elif handler(text=text, context=state.context) == -1:
            # stop scenario
            text_to_send = step['stop_iteration_text']
            self.send_text(text_to_send, user_id)
            state.delete()
        else:
            text_to_send = step['failure_text'].format(**state.context)
            self.send_text(text_to_send, user_id)


if __name__ == '__main__':
    configure_logging()
    bot = Bot(group_id=MY_GROUP, token=TOKEN)
    bot.run()
