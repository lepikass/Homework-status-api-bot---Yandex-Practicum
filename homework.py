import os
import logging
import time
import requests
from dotenv import load_dotenv
from telebot import TeleBot
import sys

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
)
logger.addHandler(handler)

# Загрузка переменных окружения
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600  # Период повторных попыток в секундах
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
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }

    missing_tokens = [name for name, value in tokens.items() if not value]

    if missing_tokens:
        logger.critical(
            f'Отсутствуют переменные окружения: {", ".join(missing_tokens)}.'
        )
        return False
    return True


def send_message(bot: TeleBot, message: str) -> None:
    """Отправляет сообщение пользователю через Telegram бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения в Telegram: {e}')


def get_api_answer(timestamp: int) -> dict:
    """Запрашивает данные о статусах домашних работ из API."""
    payload = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

        if response.status_code != 200:
            logger.error(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {response.status_code}. '
                f'Ответ: {response.text}. '
                f'Параметры запроса: {payload}'
            )
            raise Exception(f'Ошибка API: {response.status_code}')

        logger.debug(
            f'Успешный ответ API: {response.json()}. '
            f'Параметры запроса: {payload}'
        )
        return response.json()

    except requests.RequestException as e:
        logger.error(
            f'Ошибка при запросе к API: {e}. '
            f'Параметры запроса: {payload}'
        )
        return None


def check_response(response: dict) -> list:
    """Проверяет корректность ответа API и возвращает список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём.')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks".')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ "homeworks" должен быть списком.')
    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Извлекает и возвращает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Отсутствует ключ "homework_name".')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    global last_error
    if not check_tokens():
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    logger.info('Бот запущен и работает.')

    while True:
        try:
            logger.info('Запрос к API...')
            response = get_api_answer(timestamp)
            if response is None:
                continue

            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logger.debug('Отсутствие новых статусов.')

            timestamp = response.get('current_date', timestamp)

        except (TypeError, KeyError, Exception) as error:
            if isinstance(error, TypeError):
                message = f'Ошибка типа: {error}'
            elif isinstance(error, KeyError):
                message = f'Отсутствует ключ в ответе: {error}'
            else:
                message = f'Сбой в работе программы: {error}'

        finally:
            time.sleep(RETRY_PERIOD)
