import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ONE_DAY = 86400
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s,'
    + '%(levelname)s, %(message)s, %(name)s, %(funcName)s, %(lineno)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram-Чат."""
    logger.info('Попытка отправки сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение в чат отправлено')
    except Exception:
        logger.error('Ошибка отправки сообщения')
        raise Exception('Ошибка отправки сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    headers_and_params = {
        'header': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'param': {'from_date': timestamp}
    }
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=headers_and_params['header'],
            params=headers_and_params['param']
        )
    except Exception as error:
        raise Exception(f'Ошибка при запросе к API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        raise ValueError('Ошибка перевода ответа из json в Python')


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        response['homeworks'] and response['current_date']
    except KeyError:
        raise KeyError('Ошибка словаря')
    try:
        response['homeworks']
    except TypeError:
        raise TypeError('Ошибка типов')
    try:
        homework = (response['homeworks'])[0]
        return homework
    except IndexError:
        raise IndexError('Список работ пуст')


def parse_status(homework):
    """Получение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    current_timestamp = int(time.time()) - ONE_DAY
    status_message = ''
    error_message = ''
    if not check_tokens():
        logger.critical('Отсутствуют токены')
        sys.exit(1)
    while True:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != status_message:
                send_message(bot, message)
                status_message = message
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
