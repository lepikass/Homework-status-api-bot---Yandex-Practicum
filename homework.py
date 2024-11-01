import os
import logging
import time
import requests
from dotenv import load_dotenv
from telebot import TeleBot
from typing import Optional, Dict

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Загрузка переменных окружения
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 15  # Период повторных попыток в секундах
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

# Определение статусов домашних работ
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверяет наличие необходимых токенов."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.critical(
            'Отсутствует переменная окружения: "PRACTICUM_TOKEN", '
            '"TELEGRAM_TOKEN" или "TELEGRAM_CHAT_ID".'
        )
        return False
    return True


def send_message(bot: TeleBot, message: str) -> None:
    """Отправляет сообщение пользователю через Telegram бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения в Telegram: {e}')


def get_api_answer(timestamp: int) -> Optional[Dict]:
    """Запрашивает данные о статусах домашних работ из API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != 200:
            logging.error(f'Ошибка API: {response.status_code}')
            return None
        return response.json()
    except Exception as e:
        logging.error(f'Ошибка при запросе к API: {e}')
        return None


def check_response(response: dict) -> None:
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        logging.error('Ответ API должен быть словарём.')
        raise TypeError('Ответ API должен быть словарём.')

    if 'homeworks' not in response:
        logging.error('Отсутствует ключ "homeworks".')
        raise TypeError('Отсутствует ключ "homeworks".')

    if not isinstance(response['homeworks'], list):
        logging.error('Ключ "homeworks" должен быть списком.')
        raise TypeError('Ключ "homeworks" должен быть списком.')


def parse_status(homework: dict) -> str:
    """Извлекает и возвращает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        logging.error('Отсутствует ключ "homework_name".')
        raise KeyError('Отсутствует ключ "homework_name".')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logging.error(f'Неизвестный статус: {status}')
        raise ValueError(f'Неизвестный статус: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    logging.info('Бот запущен и работает.')

    while True:
        try:
            logging.info('Запрос к API...')
            response = get_api_answer(timestamp)
            if response is None:
                time.sleep(RETRY_PERIOD)
                continue
            check_response(response)
            homeworks = response['homeworks']

            if not homeworks:
                logging.debug('Отсутствие новых статусов.')
                time.sleep(RETRY_PERIOD)
                continue

            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)

            logging.info('Ожидание следующего запроса...')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
