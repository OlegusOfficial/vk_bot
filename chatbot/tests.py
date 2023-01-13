from copy import deepcopy
from unittest import TestCase

from unittest.mock import patch, Mock, ANY

from pony.orm import db_session, rollback
from vk_api.bot_longpoll import VkBotMessageEvent

from bot import Bot
from config import DEFAULT_ANSWER, INTENTS, SCENARIOS
from generate_ticket import generate_ticket
from handlers import dispatcher
from datetime import date


def isolate_db(test_func):
    def wrapper(*args, **kwargs):
        with db_session():
            test_func(*args, **kwargs)
            rollback()
    return wrapper


class TestBot(TestCase):

    RAW_EVENT = {'type': 'message_new',
                 'object': {'date': 1601834225, 'from_id': 126949929, 'id': 44,
                            'out': 0, 'peer_id': 126949929, 'text': 'здарова', 'conversation_message_id': 37,
                            'fwd_messages': [], 'important': False, 'random_id': 0,
                            'attachments': [], 'is_hidden': False},
                 'group_id': 199096923, 'event_id': 'a5505994cced934e316b399a401796efa0d68b87'}
    FLIGHTS = {
        'москва': {
            'париж': [('1', '10:00'), ('8', '10:00'), ('15', '10:00'), ('22', '10:00'), ('27', '10:00'), ('3', '12:00'),
                      ('10', '12:00'), ('17', '12:00'), ('24', '12:00')],
            'лондон': [('5', '13:00'), ('10', '13:00'), ('15', '13:00'), ('20', '15:30'), ('25', '15:30')],
            'пекин': [('2', '19:00'), ('9', '19:00'), ('16', '19:00'), ('23', '19:00'), ('15', '22:00')]
        }
    }

    def test_run(self):
        count = 5
        obj = {}
        events = [obj] * count
        long_poll_mock = Mock(return_value=events)
        long_poll_listen_mock = Mock()
        long_poll_listen_mock.listen = long_poll_mock
        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll', return_value=long_poll_listen_mock):
                bot = Bot('', '')
                bot.on_event = Mock()
                bot.send_image = Mock()
                bot.run()
                bot.on_event.assert_called()
                bot.on_event.assert_any_call(obj)
                assert bot.on_event.call_count == count

    def test_on_event(self):
        event = VkBotMessageEvent(raw=self.RAW_EVENT)
        send_mock = Mock()
        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll'):
                bot = Bot('', '')
                bot.api = Mock()
                bot.api.messages.send = send_mock

                bot.on_event(event)
        send_mock.assert_called_once_with(
            message=ANY,
            random_id=ANY,
            peer_id=self.RAW_EVENT['object']['peer_id'])

    INPUTS = ['/ticket', 'Москва', 'Париж', '01-05-2021', '1', '2', 'Мой комментарий', 'Да',
              '89261234567', 'abc@mail.ru', 'Привет', '/help']
    OUTPUTS = [step['text'].format(user_name='Олег', departure='москва', arrival='париж', date='00:00 01-05-2021',
                                   flight='01-05-2021 10:00', sits='2', comment='Мой комментарий', email='abc@mail.ru',
                                   phone_number='89261234567',
                                   flights_to_write='01-05-2021 10:00\n03-05-2021 12:00\n08-05-2021 10:00'
                                                    '\n10-05-2021 12:00\n15-05-2021 10:00'
                                   ) for step in SCENARIOS['ticket']['steps'].values()]
    OUTPUTS.extend([DEFAULT_ANSWER, INTENTS[0]['answer']])

    @isolate_db
    def test_run_ok(self):
        send_mock = Mock()
        user_ids = Mock(return_value=[{'first_name': 'Олег'}])
        api_mock = Mock()
        api_mock.messages.send = send_mock
        api_mock.users.get = user_ids
        events = []
        for input_text in self.INPUTS:
            event = deepcopy(self.RAW_EVENT)
            event['object']['text'] = input_text
            events.append(VkBotMessageEvent(event))

        long_poll_mock = Mock()
        long_poll_mock.listen = Mock(return_value=events)
        with patch('bot.VkBotLongPoll', return_value=long_poll_mock):
            bot = Bot('', '')
            bot.api = api_mock
            bot.api.users.get = api_mock.users.get
            bot.send_image = Mock()
            bot.run()

        assert send_mock.call_count == len(self.INPUTS)

        real_outputs = []
        for call in send_mock.call_args_list:
            args, kwargs = call
            real_outputs.append(kwargs['message'])

        assert real_outputs == self.OUTPUTS

    def test_dispatcher_default_case(self):
        context = {'arrival': 'пекин', 'departure': 'москва'}
        user_date = date(year=2021, month=1, day=1)
        result = dispatcher(user_date, context)
        assert result == ['02-01-2021 19:00', '09-01-2021 19:00', '15-01-2021 22:00', '16-01-2021 19:00',
                          '23-01-2021 19:00']

    def test_dispatcher_new_month_case(self):
        context = {'arrival': 'лондон', 'departure': 'москва'}
        user_date = date(year=2021, month=1, day=24)
        result = dispatcher(user_date, context)
        assert result == ['25-01-2021 15:30', '05-02-2021 13:00', '10-02-2021 13:00', '15-02-2021 13:00',
                          '20-02-2021 15:30']

    def test_dispatcher_new_year_case(self):
        context = {'arrival': 'париж', 'departure': 'москва'}
        user_date = date(year=2021, month=12, day=25)
        result = dispatcher(user_date, context)
        assert result == ['27-12-2021 10:00', '01-01-2022 10:00', '03-01-2022 12:00', '08-01-2022 10:00',
                          '10-01-2022 12:00']

    def test_image_generation(self):
        ticket_file = generate_ticket(fio='олег', from_='ff', to='ffb', flight='fsf', test=True, email='abc@mail.ru')
        with open('files/ticket_test.png', 'rb') as expected_file:
            expected_bytes = expected_file.read()

        assert ticket_file.read() == expected_bytes
