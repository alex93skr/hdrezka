import threading
import time
import configparser
import logging
import imaplib
import email
import base64

from smtplib import SMTP_SSL
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup
from fake_headers import Headers

file_log = logging.FileHandler('rez.log', 'a', 'utf-8')
console_out = logging.StreamHandler()

logging.basicConfig(
    handlers=(file_log, console_out),
    level=logging.INFO,
    format='%(asctime)s [%(module)s] %(message)s',
    datefmt='%y-%b-%d %H:%M:%S',
)

log = logging.getLogger(__name__)


def open_url_file():
    with open('rezka_url.txt', encoding='utf-8') as f:
        _url = f.read()
        log.info(f'open_url_file {_url}')
        return _url


def save_url_file(data):
    with open('rezka_url.txt', 'w', encoding='utf-8') as f:
        f.write(data)
        log.info(f'save_url_file {data}')


def fake_head():
    _headers = Headers(headers=True).generate()
    # del 'br' encoding
    if _headers.get('Accept-Encoding'):
        _headers['Accept-Encoding'] = _headers['Accept-Encoding'][:-4]
    return _headers


def site_block_rkn(url):
    url_without_http = url[url.find('//') + 2:]  # del 'http://'
    url = f'https://reestr.rublacklist.net/ru/?q={url_without_http}'

    r = requests.get(url, headers=fake_head())
    html = r.text.replace('table_td td_state ', 'table_td td_state1')
    soup = BeautifulSoup(html, 'html.parser')
    divs = soup.find('div', {'class': 'table_td td_state1'})

    if divs and divs.text == "\nзаблокирован\n":
        log.info(f'site {url} BLOCK rkn')
        return True
    else:
        log.info(f'site {url} not block rkn')


def site_available(url):
    if site_block_rkn(url):
        return False

    try:
        r = requests.get(url, headers=fake_head(), allow_redirects=False)
        # print(r.status_code)
    except Exception as err:
        log.info(f'site {url} NOT available err {err.__class__.__name__, err}')
        return False

    if r.status_code == 200:
        log.info(f'site_available code 200 {url}')
        return True
    else:
        log.info(f'site NOT available {url} code {r.status_code}')
        return False


class Appdata:
    """
    """

    REZKA_URL = open_url_file()
    # print(REZKA_URL)

    config = configparser.ConfigParser()
    config.read('hdrezka.ini')

    addr_from = config.get('Settings', 'addr_from')
    addr_to = config.get('Settings', 'addr_to')
    password = config.get('Settings', 'password')
    smtp = config.get('Settings', 'smtp')
    port = config.get('Settings', 'port')
    imap = config.get('Settings', 'imap')
    folder = config.get('Settings', 'folder')


class Checker_timer(threading.Thread):
    """

    """

    def __init__(self):
        """
        """
        threading.Thread.__init__(self)

        # self.go()

    def run(self):
        while True:
            if not site_available(Appdata.REZKA_URL):
                # запуск в поток апдейтера
                updater = Updater()
                updater.start()
                updater.go()
                updater.join()

            # час 3600
            log.info(f'sleep 3600')
            time.sleep(3600)


class Updater(threading.Thread):
    def __init__(self):
        """

        """
        threading.Thread.__init__(self)

        # self.send_email_err = False
        # self.load_email_err = False
        self.updater_error = False
        self.url = ''

        # self.go()

    def go(self):
        """
        апдейт:
        отправить почту
        проверить почту
            чек from в письме
            если непрочитаных нету
            если непрочитаных больше 1
        спарсить урл
        чекнуть урл
        обновить урл, записать на диск

        """

        log.info(f'Updater go')

        try:
            self.send_email()
        except Exception as err:
            log.info(f'send_email ERR {err}')
            return

        time.sleep(10)

        self.load_email()
        if self.updater_error: return

        try:
            self.parsing_url()
        except Exception as err:
            log.info(f'parsing_url ERR {err}')
            return

        if site_available(self.url):
            Appdata.REZKA_URL = self.url
            save_url_file(self.url)

    def send_email(self):
        # log.info(f'send_email')
        # addr_from = Appdata.addr_from  # Адресат
        # addr_to = Appdata.addr_to  # Получатель
        # password = Appdata.password

        msg = MIMEMultipart()  # Создаем сообщение
        msg['From'] = Appdata.addr_from  # Адресат
        msg['To'] = Appdata.addr_to  # Получатель
        msg['Subject'] = ''  # Тема сообщения

        body = ""
        msg.attach(MIMEText(body, 'plain'))  # Добавляем в сообщение текст

        with SMTP_SSL(host=Appdata.smtp, port=Appdata.port) as smtp:
            # smtp.noop()
            smtp.login(Appdata.addr_from, Appdata.password)
            smtp.send_message(msg)

        log.info(f'send_email done')

    def load_email(self):
        # log.info(f'load_email')

        imap = imaplib.IMAP4_SSL(Appdata.imap)
        imap.login(Appdata.addr_from, Appdata.password)
        imap.select(Appdata.folder)

        # "UNSEEN" "ALL"
        try:
            last_msg_numbers = imap.uid('search', "UNSEEN")[1][0].split()[-1]
        except Exception as err:
            log.info(f'load_email ERR {err}')
            self.updater_error = True
            return

        try:
            res, msg = imap.uid('fetch', last_msg_numbers, '(RFC822)')  # Для метода uid
            self.msg = email.message_from_bytes(msg[0][1])
        except Exception as err:
            log.info(f'load_email ERR {err}')
            self.updater_error = True
            return

        log.info(f'load_email done')

    def parsing_url(self):

        found_url = False

        for part in self.msg.walk():
            if part.get_content_maintype() == 'text' and part.get_content_subtype() == 'html':
                # print(base64.b64decode(part.get_payload()).decode())
                # print(base64.b64decode(part.get_payload()).decode())
                html = part.get_payload()
                # print(base64.b64decode(html))
                # mytext = base64.urlsafe_b64decode(html.encode('UTF-8'))
                # print(html)
                soup = BeautifulSoup(html, 'html.parser')
                rezka_link = soup.find('a').attrs['href'][3:-2]
                # '3D"http://hdrezkahffrtq.net/"'
                # print(rezka_link)
                self.url = rezka_link
                found_url = True
                log.info(f'parsing_url {self.url} done')

                break

        if not found_url:
            log.info(f'parsing_url NO URL')


if __name__ == "__main__":
    file_log = logging.FileHandler('rez.log', 'a', 'utf-8')
    console_out = logging.StreamHandler()

    logging.basicConfig(
        handlers=(file_log, console_out),
        level=logging.INFO,
        format='%(asctime)s [%(module)s] %(message)s',
        datefmt='%y-%b-%d %H:%M:%S',
    )

    appdata = Appdata()

    # updater = Updater()
    # updater.start()
    # updater.go()
    # updater.send_email()
    # updater.load_email()
    # updater.parsing_url()
    # print(updater.url)
    # updater.join()

    checker = Checker_timer()
    checker.start()
    # checker.go()
    checker.join()
