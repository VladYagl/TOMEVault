import bs4
import re
import urllib.request
import pickle
import colorama
import numpy as np
from bs4 import BeautifulSoup

colorama.init()
tome_link = 'https://te4.org'
vault_link = f'{tome_link}/characters-vault'
save_file = 'chars.pickle'

# update filter list
# page = urllib.request.urlopen(vault_link)
# with open("filters.html", "w", encoding="utf-8") as fp:
#     fp.write(page.read().decode('utf-8'))
#     exit()


class VaultSoup:
    def __init__(self):
        with open("filters.html", "r", encoding="utf-8") as fp:
            self.soup = BeautifulSoup(fp.read(), 'html.parser')
        self.filters = {}
        for filter_name in ['difficulty', 'permadeath', 'race', 'class', 'campaign']:
            self.filters[filter_name] = self.get_filter_values(filter_name)
        # Get the latest game version
        games = self.get_filter_values('game', get_all=True)
        self.game = next(iter(games.values()))
        self.save_chars = {}
        try:
            with open(save_file, 'rb') as fp:
                self.save_chars = pickle.load(fp)
        except:
            pass

    @staticmethod
    def tag(name):
        return f'tag_{name}[]'

    def get_filter_values(self, filter_name, get_all=False):
        values = {}
        for op in self.soup.find('select', {'name': self.tag(filter_name)}).contents:
            if type(op) is bs4.element.Tag and (op.get('data-official') or get_all):
                values[op.contents[0]] = op.get('value')
        return values

    @staticmethod
    def get_talents(talents_type, soup):
        talents = soup.find('h4', text=re.compile(talents_type)).parent.find_all('tr')

        build = {}
        cur_cat = None
        for talent in talents:
            li = talent.find('li')
            if li:
                eff_label = talent.find('span', text=re.compile('Effective talent level.*'))
                if not eff_label:
                    # This shit is in japanese again
                    return None
                effective_level = float(eff_label.find_next().text)

                build[cur_cat]['talents'][str(li.contents[-1])] = {
                    'points': int(talent.find_all('td')[-1].text.split('/')[0]),
                    'effective_level': effective_level
                }

            else:
                td = talent.find_all('td')
                cur_cat = td[0].text
                build[cur_cat] = {}
                build[cur_cat]['value'] = td[1].text
                build[cur_cat]['talents'] = {}
        return build

    @staticmethod
    def get_table(table_name, soup, as_list=None):
        title = soup.find('h4', text=re.compile(table_name))
        if not title:
            return None
        rows = title.parent.find_all('tr')
        if as_list is not None:
            stats = []
        else:
            stats = {}
        for row in rows:
            td = row.find_all('td')
            if as_list is not None:
                tag = td[as_list].find('li')
                if not tag:
                    tag = td[as_list]
                stats.append(str(tag.contents[-1]))
            else:
                stats[td[0].text] = td[1].text
        return stats

    def request(self, filters, min_level="", max_level="", winner=True,
                official_addons=True):

        all_chars = []
        # TODO: cache pages, but not save all of them like characters
        for page in range(10):
            print(f'scrapping page #{page}')
            req = vault_link + '?'
            req += 'tag_name='
            req += '&tag_level_min=' + str(min_level)
            req += '&tag_level_max=' + str(max_level)
            req += '&tag_game[]=' + str(self.game)
            if winner:
                req += '&tag_winner=winner'
            if official_addons:
                req += '&tag_official_addons=1'
            for filter_name in filters:
                for value in filters[filter_name]:
                    req += '&' + self.tag(filter_name) + '=' + self.filters[filter_name][value]
            req += '&page=' + str(page)
            req += '#'
            print(req)
            chars = BeautifulSoup(
                urllib.request.urlopen(req).read(), 'html.parser'
            ).find('div', {'id': 'characters'})
            chars = chars.find('tbody').find_all('a')
            if not chars:
                break
            all_chars.extend([x['href'] for x in chars if x['href'].startswith('/characters')])

        print('Done\n')

        chars = []
        for char in all_chars:
            print(tome_link + char)
            if char in self.save_chars:
                if self.save_chars[char]:
                    chars.append(self.save_chars[char])
                else:
                    print('Skipped')
                print('Loaded')
                continue
            soup = BeautifulSoup(urllib.request.urlopen(tome_link + char).read(), 'html.parser')
            build = {}
            build['name'] = soup.find('div', {'id': 'title-container'}).text
            build['class'] = self.get_talents('Class Talents', soup)
            if not build['class']:
                # Japanese shit again
                self.save_chars[char] = None
                print('Skipped')
                continue
            build['generic'] = self.get_talents('Generic Talents', soup)
            build['stats'] = self.get_table('Primary Stats', soup)
            build['vision'] = self.get_table('Vision', soup)
            build['resources'] = self.get_table('Resources', soup)
            build['speed'] = self.get_table('Speed', soup)

            build['off_mind'] = self.get_table('Offense: Mind', soup)
            build['off_spell'] = self.get_table('Offense: Spell', soup)
            build['off_pen'] = self.get_table('Offense: Damage Penetration', soup)
            build['off_bonus'] = self.get_table('Offense: Damage Bonus', soup)

            build['off_bare'] = self.get_table('Offense: Barehand', soup)
            build['off_main'] = self.get_table('Offense: Mainhand', soup)
            build['off_off'] = self.get_table('Offense: Offhand', soup)

            build['def_base'] = self.get_table('Defense: Base', soup)
            build['def_res'] = self.get_table('Defense: Resistances', soup)
            build['def_immune'] = self.get_table('Defense: Immunities', soup)

            build['prodigies'] = self.get_table('Prodigies', soup, 0)
            build['inscriptions'] = self.get_table('Inscriptions', soup, 1)

            chars.append(build)
            self.save_chars[char] = build

        with open(save_file, 'wb') as fp:
            pickle.dump(self.save_chars, fp)
        return chars


class Category:
    def __init__(self):
        self.taken = 0
        self.talents = {}

    def __repr__(self):
        return str(self.taken) + ' ' + str(self.talents)

    def take(self):
        self.taken += 1

    def add(self, name, talent):
        cnt = self.talents.get(name, [0] * 6)
        cnt[talent['points']] += 1
        self.talents[name] = cnt


def colored_perc(value, maximum, just_color=False, thresholds=[33, 66, 100]):
    perc = int((value / maximum) * 100)
    if perc < thresholds[0]:
        color = colorama.Fore.RED
    elif perc < thresholds[1]:
        color = colorama.Fore.YELLOW
    elif perc < thresholds[2]:
        color = colorama.Fore.GREEN
    else:
        color = colorama.Fore.CYAN
    if just_color:
        return color
    return color + str(perc) + '%' + colorama.Style.RESET_ALL


def plot_talents(talents_type, chars):
    cats = {}  # meow
    for char in chars:
        talents = char[talents_type]
        for cat_name in talents:
            cat = cats.get(cat_name, Category())
            cat.take()
            for talent_name, talent in talents[cat_name]['talents'].items():
                cat.add(talent_name, talent)
            cats[cat_name] = cat

    for cat_name, cat in cats.items():
        cat_desc = cat_name + ' ' + colored_perc(cat.taken, len(chars))
        print(f'{cat_desc:42} 0/5 1/5 2/5 3/5 4/5 5/5')
        for talent, stat in cat.talents.items():
            print(f'\t{talent:25}', end='')
            for i in stat:
                print(' ' + colored_perc(i, cat.taken, True, [20, 40, 100]) + f'{i:^3}' +
                      colorama.Style.RESET_ALL, end='')
            print()
        print()


def plot_stats(chars):
    stats = {}
    for char in chars:
        for key, value in char['stats'].items():
            if key not in stats:
                stats[key] = {'real': [], 'base': []}
            # <Stat-name> n (base m)
            stats[key]['real'].append(float(value.split(' ')[0]))
            stats[key]['base'].append(float(list(filter(None, re.split(' |\)|\(', value)))[-1]))
    for key, stat in stats.items():
        print("{:13} {:5.1f} (base {:5.1f})".format(key, np.average(stat['real']),
                                                    np.average(stat['base'])))


def plot_list(list_type, chars):
    size = []
    items = {}
    for char in chars:
        if not char[list_type]:
            size.append(0)
            continue
        size.append(len(char[list_type]))
        for value in char[list_type]:
            items[value] = items.get(value, 0) + 1
    print("Number: {:.1f}".format(np.average(size)))
    for key, value in sorted(items.items(), key=lambda item: -item[1]):
        print(key, colored_perc(value, len(chars)))


def main():
    # chars = VaultSoup().request({'difficulty': ['insane', 'madness'], 'class': ['brawler']},
    #                             winner=True)
    chars = VaultSoup().request({'difficulty': ['insane', 'madness'], 'class': ['anorithil']},
                                min_level=12, max_level=25, winner=False)

    print('\n\n\n\n\t------< CLASS TALENTS >------\n')
    plot_talents('class', chars)
    print('\n\n\t------< GENERIC TALENTS >------\n')
    plot_talents('generic', chars)
    print('\n\n\t------< PRIMARY STATS >------\n')
    plot_stats(chars)
    print('\n\n\t------< INSCRIPTIONS >------\n')
    plot_list('inscriptions', chars)
    print('\n\n\t------< PRODIGIES >------\n')
    plot_list('prodigies', chars)


if __name__ == "__main__":
    main()
