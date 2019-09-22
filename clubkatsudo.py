# -*- coding: utf-8 -*-

import base64
import datetime as dt
import logging
import os.path
import re
from lxml import etree
from dataclasses import dataclass
from operator import itemgetter
from sys import path

import click
import requests
import toml
from requests_html import HTML, HTMLSession
from reportlab.graphics import renderPM
from svglib.svglib import SvgRenderer

APP_NAME = 'cktool'

def line_notify(channel_secret, channel_access_token, chat_id, message, image_url):
    # originalContentUrl (max 1000 chars)
    # Max resolution: 1024 x 1024, Max file size: 1 MB

    # previewImageUrl (max 1000 chars)
    # Max resolution: 240 x 240, Max file size: 1 MB

    url = "https://api.line.me/v2/bot/message/push"
    auth = {"Authorization": f"Bearer {channel_access_token}"}
    payload = {
        "to": chat_id,
        "messages": [
            {
                "type": "text",
                "text": message
            },
            {
                "type": "image",
                "originalContentUrl": f"{image_url}",
                "previewImageUrl": f"{image_url}"
            },
            ]}
    s = requests.Session()
    s.headers.update(auth)
    r = s.post(url, json=payload)
    if r.status_code == 200:
        click.echo("Succesfully sent message")
    else:
        click.echo(f"Error sending message: {r.content} [{r.status_code}]")

def imgur_upload(client_id, client_secret, image_path, token_file):
    s = requests.Session()

    if not os.path.isfile(token_file):
        # If no refresh token exists then need user intervention to get first access token
        click.echo(f"https://api.imgur.com/oauth2/authorize?client_id={client_id}&response_type=token&state=")
        access_token = click.prompt('Enter access token from the above link (can find it in address bar after `redirect`):')
        refresh_token = click.prompt('Also enter refresh token from the above link (can find it in address bar after `redirect`):')
        with open(token_file, "w") as f:
            f.write(refresh_token)
    else:
        with open(token_file) as f:
            refresh_token = f.read().rstrip()

        # get access token using refresh token
        url = 'https://api.imgur.com/oauth2/token'
        payload = {
            'refresh_token': f'{refresh_token}',
            'client_id': f'{client_id}',
            'client_secret': f'{client_secret}',
            'grant_type': 'refresh_token'
        }
        r = s.post(url, data=payload)

        if r.status_code == 200:
            values = r.json()
            access_token = values['access_token']
            expiry = dt.datetime.now() + dt.timedelta(seconds=int(values['expires_in']))
        else:
            # TODO
            raise RequestError

    with open(image_path, 'rb') as f:
        image_data = f.read()
    b64 = base64.b64encode(image_data)

    auth = {"Authorization": f"Bearer {access_token}"}
    s.headers.update(auth)
    url = 'https://api.imgur.com/3/image'
    payload = {
        'image': b64,
        'type': 'base64',
    }
    r = s.post(url, data=payload)
    return r.json()['data']['link']


@dataclass
class Player:
    display_name: str
    actual_name: str
    status: str = 'non'
    attendance: str = 'no'


def create_formation_image(names_list, GK_name=None):
    ''' Create soccer formation image using names of attending players. '''
    with open("formation.svg") as f:
        svg_data = f.read()
        svg_data = svg_data.replace('_z_', str(len(names_list)))
        if GK_name and GK_name in names_list:
            svg_data = svg_data.replace(f'_GK_', GK_name)
            names_list.remove(GK_name)

        for i, _ in enumerate(names_list.copy(), start=1):
            svg_data = svg_data.replace(f'_x{i}_', names_list.pop())

        for i in range(1,30):
            svg_data = svg_data.replace(f'_x{i}_', '?')

    svg_root = etree.fromstring(svg_data, parser=etree.XMLParser(remove_comments=True, recover=True))
    svgRenderer = SvgRenderer(path="")
    drawing = svgRenderer.render(svg_root)
    filename = 'formation_{}.png'.format(dt.datetime.now().strftime('%Y%m%d_%Hh%Mm%Ss'))
    renderPM.drawToFile(drawing, filename, fmt="PNG")
    return filename


def parse_name(raw_name_str):
    player_name = raw_name_str.strip()  # remove ASCII whitespace.
    player_name = re.sub(r'\s+', '', player_name)  # remove Unicode whitespace chars.
    return player_name


def create_dir(ctx, param, directory):
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    return directory


def new_config_file(config_file_path):
    default_config = {
        'Main': {
            'username': "username for clubkatsudo.com",
            'club_id': 999,
            'GK_name': "name",
            'message_footer': "optional string to add to end of notification message",
        },
        'LINE': {
            'channel_secret': "fillthisin",
            'channel_access_token': "fillthisin",
            'chat_id': "fillthisin",
        },
        'Imgur': {
            'client_id': "fillthisin",
            'client_secret': "fillthisin",
        },

    }
    toml.dump(default_config, open(config_file_path, mode='w'))


def configure_logging(log_dir):
    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)

    log_folder = os.path.join(log_dir, 'logs')
    if not os.path.exists(log_folder):
        os.makedirs(log_folder, exist_ok=True)

    log_filename = f"{APP_NAME}_{dt.datetime.now().strftime('%Y%m%d_%Hh%Mm%Ss')}.log"
    log_filepath = os.path.join(log_folder, log_filename)
    log_handler = logging.FileHandler(log_filepath)

    log_format = logging.Formatter(
        fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    # Lower requests module's log level so that OAUTH2 details aren't logged
    logging.getLogger('requests').setLevel(logging.WARNING)


@click.command()
@click.option(
    '--set-password',
    is_flag=True,
    help='Set password for clubkatsudo.com account. Will be base64 encoded and stored in config file',
)
@click.option(
    '--date',
    type=click.DateTime(formats=['%Y%m%d']),
    help='YYYYMMDD of the event to scrape.',
)
@click.option(
    '--dryrun', is_flag=True, default=False,
    help='Display final message but do not send.'
)
@click.option(
    '--config-dir',
    type=click.Path(),
    default=os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')), APP_NAME),
    callback=create_dir,
    help=f'Path to directory containing config file. Defaults to $XDG_CONFIG_HOME/{APP_NAME}.',
)
@click.option(
    '--cache-dir',
    type=click.Path(),
    default=os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), APP_NAME),
    callback=create_dir,
    help=f'Path to directory to store logs and such. Defaults to $XDG_CACHE_HOME/{APP_NAME}.',
)
def main(set_password, date, dryrun, config_dir, cache_dir):
    configure_logging(cache_dir)
    config_file_path = os.path.join(config_dir, 'config.toml')
    logging.debug('Using config file: %s.', config_file_path)
    try:
        config = toml.load(open(config_file_path))
    except FileNotFoundError:
        new_config_file(config_file_path)
        click.echo(f"Default config created at {config_file_path}. Edit file and run again.")
        return 1

    if not set_password and not config['Main'].get('password_b64', None):
        click.echo("Password entry not found in config. Rerun with `--set-password` to set.")
        return 1
    elif set_password:
        password = click.prompt(f"Enter password for {config['Main']['username']} at clubkatsudo.com")
        config['Main']['password_b64'] = str(base64.b64encode(password.encode("utf-8")), "utf-8")
        toml.dump(config, open(config_file_path, mode='w'))
    else:
        password =  str(base64.b64decode(config['Main']['password_b64']), "utf-8")

    imgur_token_file = os.path.join(cache_dir, 'imgur_refresh_token')

    # Load list of players from text file. This is needed for two reasons.
    # 1. To give proper display names for each player scraped from the site
    # 2. To give status for each player - 0 = former member, 1 = registered & playing, etc.
    # See README for more info.
    # File format: display name, actual name, status
    cwd = path[0]
    player_list_path = os.path.join(config_dir, 'registered_players.txt')
    player_list = {}
    if os.path.isfile(player_list_path):
        with open(player_list_path) as file:
            for line in file:
                line = line.strip()
                display_name, actual_name, status = line.split(',')
                player_list[display_name] = Player(display_name, actual_name, status)
    print(f'No. players in text file: {len(player_list)}')

    # Login to website.
    s = HTMLSession()
    tld = 'https://clubkatsudo.com'
    r = s.get(tld)

    login_data = {
        '__VIEWSTATE': r.html.find('#__VIEWSTATE', first=True).attrs['value'],
        '__EVENTVALIDATION': r.html.find('#__EVENTVALIDATION', first=True).attrs['value'],
        'txtUserID': config['Main']['username'],
        'txtPassword': password,
        'btnLogin.x': 42,
        'btnLogin.y': 8,
    }
    r = s.post(tld, data=login_data)

    #with open("step1_postlogin", "wb") as f:
    #    f.write(r.content)

    # Get attendance
    # TODO: Handle multiple events on the same day (&no=1 in the URL)
    event_url = f"{tld}/myclub_scheduleref.aspx?code={config['Main']['club_id']}&ymd={date}&no=1&group="
    r = s.get(event_url)

    # requests is borking the encoding for html.text
    r = HTML(html=r.content.decode('shift-jis'))
    if not r.find('#lblShukketsu'):
        raise SystemExit(f'No events for {date}')
    shusseki = r.find('#lblShukketsu', first=True).find('[style*="000099"]', first=True).text
    kesseki = r.find('#lblShukketsu', first=True).find('[style*="cc0000"]', first=True).text
    mitei = r.find('#lblShukketsu', first=True).find('[style*="999999"]', first=True).text

    rows = r.find('#gvDetail', first=True).find('tr')
    for row in rows:
        cells = row.find('td')
        player_name = parse_name(cells[1].text)
        attendance_icon = cells[0].find('img', first=True).attrs['src']
        if 'batsu' in attendance_icon:
            shukketsu = 'no'
        elif 'maru' in attendance_icon:
            shukketsu = 'yes'
        else:
            shukketsu = 'unknown'
        try:
            player_list[player_name].attendance = shukketsu
        except KeyError:
            player_list[player_name] = Player(player_name, player_name, 1)
            player_list[player_name].attendance = shukketsu

    title = r.find('#lblNaiyo', first=True).text
    date = r.find('#lblNittei', first=True).text
    place = r.find('#lblBasho', first=True).text
    desc = r.find('#lblBiko', first=True).text

    message = f"\u26BD{title}\u26BD\n【出欠】\u2B55{shusseki}人 \u274C{kesseki}人\n【日付】{date}\n【場所】{place}\n【詳細】{desc}\n\n出欠登録: https://clubkatsudo.com/myclub_editpresence.aspx?code={config['Main']['club_id']}\n\n{config['Main']['message_footer']}"

    attending_list = []
    [attending_list.append(v.actual_name) for k,v in player_list.items() if v.attendance == 'yes']
    image_file_path = create_formation_image(attending_list, config['Main']['GK_name'])
    image_url = imgur_upload(config['Imgur']['client_id'], config['Imgur']['client_secret'], image_file_path, imgur_token_file)
    # The reason for encoding when printing is because of the emojis being used:
    # UnicodeEncodeError: 'utf-8' codec can't encode characters in position xx: surrogates not allowed
    print(message.encode('utf-16', 'surrogatepass').decode('utf-16'))
    print(image_url)
    message_ok = False
    while not message_ok:
        if click.confirm('Edit before sending?'):
            edited_message = click.edit(text=message.encode('utf-16', 'surrogatepass').decode('utf-16'))
            if edited_message:
                message = edited_message
            print(message.encode('utf-16', 'surrogatepass').decode('utf-16'))
            if click.confirm('Use this message?'):
                message_ok = True
        else:
            message_ok = True
    if dryrun:
        click.echo("Exiting without sending message.")
    else:
        if click.confirm('Send message?', abort=True):
            # TODO: check existence of config items
            line_notify(config['LINE']['channel_secret'], config['LINE']['channel_access_token'], config['LINE']['chat_id'], message, image_url)

if __name__ == '__main__':
    main()
