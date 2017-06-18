import datetime as dt
import os.path
import re
from operator import itemgetter
from sys import path

import click
import pyperclip
import requests
from bs4 import BeautifulSoup
from tabulate import tabulate


def validate_date(ctx, param, date):
    try:
        date = dt.datetime.strptime(date, "%Y%m%d")
    except ValueError:
        raise click.BadParameter('Date should be in YYYYMMDD format')
    return date.strftime("%Y/%m/%d")


@click.command()
@click.argument('username')
@click.option('--club', '-c', 'club_id', prompt='Enter club ID', type=int)
@click.option('--date', '-d', default=dt.datetime.today().strftime("%Y%m%d"),
              callback=validate_date, expose_value=True,
              help='YYYYMMDD of the event to scrape')
@click.option('--password', '-p', prompt=True, hide_input=True,
              confirmation_prompt=False)
def main(username, password, date, club_id):
    # Load list of players from text file. This is needed for two reasons.
    # 1. To give proper display names for each player scraped from the site
    # 2. To give status for each player - 0 = former member, 1 = registered & playing, etc. See README for more info.
    cwd = path[0]
    player_list_path = os.path.join(cwd, 'registered_players.txt')
    player_list = {}
    if os.path.isfile(player_list_path):
        with open(player_list_path, 'r') as file:
            for line in file:
                line = line.strip()
                player_list[line.split(',')[0]] = [line.split(',')[1], line.split(',')[2]]
    print(f"No. players in text file: {len(player_list)}")

    # Get yes/no list - note that the unanswered list has to be gotten separately
    url = "http://clubkatsudo.com/index.aspx"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko"}
    s = requests.Session()
    s.headers.update(headers)
    r = s.get(url)
    soup = BeautifulSoup(r.content.decode('shift_jisx0213', 'ignore'), "html.parser")

    login_data = {
        "__VIEWSTATE": soup.find(id="__VIEWSTATE")['value'],
        "__EVENTVALIDATION": soup.find(id="__EVENTVALIDATION")['value'],
        "txtUserID": username,
        "txtPassword": password,
        "btnLogin.x": "55",
        "btnLogin.y": "17",
    }
    s.post(url, data=login_data)

    event_url = f"http://clubkatsudo.com/myclub_scheduleref.aspx?code={club_id}&ymd={date}&no=1&group="
    r = s.get(event_url)
    soup = BeautifulSoup(r.content.decode('shift_jisx0213', 'ignore'), "html.parser")

    if not soup.find('span', id="lblShukketsu").contents:
        raise SystemExit(f"No events for {date}")

    print("Raw numbers from clubkatsudo.com:")
    print("出席: " + soup.find('span', attrs={'style': 'font-weight:bold;color:#000099'}).string)
    print("欠席: " + soup.find('span', attrs={'style': 'font-weight:bold;color:#cc0000'}).string)
    print("未定: " + soup.find('span', attrs={'style': 'font-weight:bold;color:#999999'}).string)

    table = soup.find('table', id="gvDetail")
    details = {}
    for row in table.find_all('tr'):
        cells = row.find_all('td')

        player_name = cells[1].get_text(strip=True)
        player_name = re.sub(r"\s+", "", player_name)  # remove Unicode whitespace characters as well

        if 'batsu' in cells[0].img['src']:
            shukketsu = '✗'
        elif 'maru' in cells[0].img['src']:
            shukketsu = '●'
        else:
            shukketsu = '▲'

        details[player_name] = shukketsu

    form_url = f"http://clubkatsudo.com/myclub_scheduleref.aspx?code={club_id}&ymd={date}&no=1&from=top"
    form_data = {
        "__VIEWSTATE": soup.find(id="__VIEWSTATE")['value'],
        "__EVENTVALIDATION": soup.find(id="__EVENTVALIDATION")['value'],
        "__EVENTTARGET": "lnkMikaitou",
        "__EVENTARGUMENT": "",
    }
    r = s.post(form_url, data=form_data)
    soup = BeautifulSoup(r.content.decode('shift_jisx0213', 'ignore'), "html.parser")

    # Get unanswered list - this is hidden behind JS in browser hence need to get separately
    table = soup.find('table', id="gvDetail_Mikaitou")
    print("　未: {0}人".format(len(table.find_all('tr'))))
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        player_name = cells[0].get_text(strip=True)
        player_name = re.sub(r"\s+", "", player_name)
        details[player_name] = '未'

    # Remove non-players and output final list as HTML
    details_reg = {}
    for player in details:
        if player in player_list and player_list[player][1] in ('1', '2'):
            details_reg[player_list[player][0]] = details[player]

    sorted_list = sorted([[k, v] for k, v in details_reg.items()], key=itemgetter(1), reverse=False)

    print("Final numbers:")
    print("出席: {}人".format(len([[k, v] for k, v in details_reg.items() if v == '●'])))
    print("欠席: {}人".format(len([[k, v] for k, v in details_reg.items() if v == '✗'])))
    print("未定: {}人".format(len([[k, v] for k, v in details_reg.items() if v == '▲'])))
    print("　未: {}人".format(len([[k, v] for k, v in details_reg.items() if v == '未'])))

    pyperclip.copy(tabulate(sorted_list, headers=['Name', 'y/n'], tablefmt="html"))
    print("Check clipboard for final list in HTML format.")

if __name__ == '__main__':
    main()
