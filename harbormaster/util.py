#!/usr/bin/env python

import sys
import urllib,re
import sqlite3

#con = sqlite3.connect('ais.db3')
#cx = sqlite3.connect('test.db3')
#cu = cx.cursor()

position_types = [1,2,3,18,19]

def strip_text(input):
    if input is None:
        return None
    return input.rstrip('@').rstrip(' ').lstrip(' ')

def get_mid_from_mmsi(mmsi):
    if(mmsi[0] in ['2', '3', '4', '5', '6', '7']):
        return (mmsi[0:3], 'Ship')
    elif(mmsi[0:2] == '00'):
        return (mmsi[2:5], 'Coast Radio Station')
    elif(mmsi[0] == '0'):
        return (mmsi[1:4], 'Group of Ships')
    elif(mmsi[0:3] == '111'):
        return (mmsi[3:6], 'SAR Aircraft')
    elif(mmsi[0:2] == '99'):
        return (mmsi[2:5], 'Aid to Navigation')
    elif(mmsi[0:2] == '98'):
        return (mmsi[2:5], 'Daughter Vessel')
    elif(mmsi[0:3] == '970'):
        return ('000', 'SAR Transmitter')
    elif(mmsi[0:3] == '972'):
        return ('000', 'Man Overboard')
    elif(mmsi[0:3] == '974'):
        return ('000', 'EPIRB')

navigation_status = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuverability",
    4: "Constrained by her draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Under way sailing",
    9: "Reserved",
    10: "Reserved",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "AIS-SART is active",
    15: "" # Undefined default
}

def get_navigation_text(value):
    try:
        return navigation_status[value]
    except KeyError:
        return "Unknown"

ship_type_major = {
    1: 'Reserved',
    2: 'Wing In Ground',
    4: 'High-Speed Craft',
    6: 'Passenger',
    7: 'Cargo',
    8: 'Tanker',
    9: 'Other'
}

ship_type_minor = {
    30: 'Fishing',
    31: 'Towing',
    32: 'Towing (Large)',
    33: 'Dredger',
    34: 'Dive Vessel',
    35: 'Military Ops',
    36: 'Sailing Vessel',
    37: 'Pleasure Craft',
    38: 'Reserved',
    39: 'Reserved',
    50: 'Pilot Vessel',
    51: 'Search and Rescue',
    52: 'Tug',
    53: 'Port Tender',
    54: 'Anti-Pollution',
    55: 'Law Enforcement',
    56: 'Local Vessel',
    57: 'Local Vessel',
    58: 'Medical Transport',
    59: 'Noncombatant Vessel'
}

def readable_ship_type(ship_type):
    if(ship_type is None):
        return "Unknown"

    first_digit = int(str(ship_type)[:1])
    if(first_digit in ship_type_major.keys()):
        return ship_type_major[first_digit]
    elif(ship_type in ship_type_minor.keys()):
        return ship_type_minor[ship_type]
    else:
        return 'Unknown'

# From Schwehr's libais utilities
def mmsi_codes(filename=None):
    '''Create a table of 3 digit MMSI codes
    @return: code lookup table
    @rtype: dict
    '''

    entry_re_str = r'''\<tr\>\<td\>(?P<prefixes>[0-9 ,]*)\</td\>\<td\>(?P<country>[^<]*)\</td\>\</tr\>'''
    entry_re = re.compile(entry_re_str)

    if not filename:
        html = urllib.urlopen('http://www.itu.int/cgi-bin/htsh/glad/cga_mids.sh?lng=E')
    else:
        html = file(filename)

    # Lame parser.  Would be better to use BeautifulSoup or html5lib
    last_country = None
    codes = {}
    for line in html:
        if '<tr>' != line[0:4]: continue
        matches = entry_re.search(line)
        if not matches: continue

        prefixes = matches.group('prefixes')
        country = matches.group('country')

        if chr(244) in country:
            country = country.replace(chr(244),'o')
        if ' - ' == country:
            country = last_country

        for prefix in prefixes.split(','):
            codes[int(prefix)] = country

        last_country = country

    return codes

iso_2alpha = {
    "Adelie Land - France": 'adelie',
    "Afghanistan": 'af',
    "Alaska (State of) - United States of America": 'alaska',
    "Albania (Republic of)": 'al',
    "Algeria (People's Democratic Republic of)": 'dz',
    "American Samoa - United States of America": 'as',
    "Andorra (Principality of)": 'ad',
    "Angola (Republic of)": 'ao',
    "Anguilla - United Kingdom of Great Britain and Northern Ireland": 'ai',
    "Antigua and Barbuda": 'ag',
    "Argentine Republic": 'ar',
    "Armenia (Republic of)": 'am',
    "Aruba - Netherlands (Kingdom of the)": 'aw',
    "Ascension Island - United Kingdom of Great Britain and Northern Ireland": 'sh',
    "Australia": 'au',
    "Austria": 'at',
    "Azerbaijan (Republic of)": 'az',
    "Azores - Portugal": 'azores',
    "Bahamas (Commonwealth of the)": 'bs',
    "Bahrain (Kingdom of)": 'bh',
    "Bangladesh (People's Republic of)": 'bd',
    "Barbados": 'bb',
    "Belarus (Republic of)": 'by',
    "Belgium": 'be',
    "Belize": 'bz',
    "Benin (Republic of)": 'bj',
    "Bermuda - United Kingdom of Great Britain and Northern Ireland": 'bm',
    "Bhutan (Kingdom of)": 'bt',
    "Bolivia (Plurinational State of)": 'bo',
    "Bosnia and Herzegovina": 'ba',
    "Botswana (Republic of)": 'bw',
    "Brazil (Federative Republic of)": 'br',
    "British Virgin Islands - United Kingdom of Great Britain and Northern Ireland": 'vg',
    "Brunei Darussalam": 'bn',
    "Bulgaria (Republic of)": 'bg',
    "Burkina Faso": 'bf',
    "Burundi (Republic of)": 'bi',
    "Cabo Verde (Republic of)": 'cv',
    "Cambodia (Kingdom of)": 'kh',
    "Cameroon (Republic of)": 'cm',
    "Canada": 'ca',
    "Cayman Islands - United Kingdom of Great Britain and Northern Ireland": 'ky',
    "Central African Republic": 'cf',
    "Chad (Republic of)": 'td',
    "Chile": 'cl',
    "China (People's Republic of)": 'cn',
    "Christmas Island (Indian Ocean) - Australia": 'cx',
    "Cocos (Keeling) Islands - Australia": 'cc',
    "Colombia (Republic of)": 'co',
    "Comoros (Union of the)": 'km',
    "Congo (Republic of the)": 'cg',
    "Cook Islands - New Zealand": 'ck',
    "Costa Rica": 'cr',
    "Cote d'Ivoire (Republic of)": 'cr',
    "Croatia (Republic of)": 'hr',
    "Crozet Archipelago - France": 'tf',
    "Cuba": 'cu',
    "Cura\xe7ao - Netherlands (Kingdom of the)": 'cw',
    "Cyprus (Republic of)": 'cy',
    "Czech Republic": 'cz',
    "Democratic People's Republic of Korea": 'kp',
    "Democratic Republic of the Congo": 'cd',
    "Denmark": 'dk',
    "Djibouti (Republic of)": 'dj',
    "Dominica (Commonwealth of)": 'dm',
    "Dominican Republic": 'do',
    "Ecuador": 'ec',
    "Egypt (Arab Republic of)": 'eg',
    "El Salvador (Republic of)": 'sv',
    "Equatorial Guinea (Republic of)": 'gq',
    "Eritrea": 'er',
    "Estonia (Republic of)": 'ee',
    "Ethiopia (Federal Democratic Republic of)": 'et',
    "Falkland Islands (Malvinas) - United Kingdom of Great Britain and Northern Ireland": 'fk',
    "Faroe Islands - Denmark": 'fo',
    "Fiji (Republic of)": 'fj',
    "Finland": 'fi',
    "France": 'fr',
    "French Polynesia - France": 'pf',
    "Gabonese Republic": 'ga',
    "Gambia (Republic of the)": 'gm',
    "Georgia": 'ge',
    "Germany (Federal Republic of)": 'de',
    "Ghana": 'gh',
    "Gibraltar - United Kingdom of Great Britain and Northern Ireland": 'gi',
    "Greece": 'gr',
    "Greenland - Denmark": 'gl',
    "Grenada": 'gr',
    "Guadeloupe (French Department of) - France": 'gp',
    "Guatemala (Republic of)": 'gt',
    "Guiana (French Department of) - France": 'gf',
    "Guinea (Republic of)": 'gn',
    "Guinea-Bissau (Republic of)": 'gw',
    "Guyana": 'gy',
    "Haiti (Republic of)": 'ht',
    "Honduras (Republic of)": 'hn',
    "Hong Kong (Special Administrative Region of China) - China (People's Republic of)": 'hk',
    "Hungary": 'hu',
    "Iceland": 'is',
    "India (Republic of)": 'in',
    "Indonesia (Republic of)": 'id',
    "Iran (Islamic Republic of)": 'ir',
    "Iraq (Republic of)": 'iq',
    "Ireland": 'ie',
    "Israel (State of)": 'il',
    "Italy": 'it',
    "Jamaica": 'jm',
    "Japan": 'jp',
    "Jordan (Hashemite Kingdom of)": 'jo',
    "Kazakhstan (Republic of)": 'kz',
    "Kenya (Republic of)": 'ke',
    "Kerguelen Islands - France": 'tf',
    "Kiribati (Republic of)": 'ki',
    "Korea (Republic of)": 'kr',
    "Kuwait (State of)": 'kw',
    "Kyrgyz Republic": 'kg',
    "Lao People's Democratic Republic": 'la',
    "Latvia (Republic of)": 'lv',
    "Lebanon": 'lb',
    "Lesotho (Kingdom of)": 'ls',
    "Liberia (Republic of)": 'lr',
    "Libya": 'ly',
    "Liechtenstein (Principality of)": 'li',
    "Lithuania (Republic of)": 'lt',
    "Luxembourg": 'lu',
    "Macao (Special Administrative Region of China) - China (People's Republic of)": 'mo',
    "Madagascar (Republic of)": 'mg',
    "Madeira - Portugal": 'madeira',
    "Malawi": 'mw',
    "Malaysia": 'my',
    "Maldives (Republic of)": 'mv',
    "Mali (Republic of)": 'ml',
    "Malta": 'mt',
    "Marshall Islands (Republic of the)": 'mh',
    "Martinique (French Department of) - France": 'mq',
    "Mauritania (Islamic Republic of)": 'mr',
    "Mauritius (Republic of)": 'mu',
    "Mexico": 'mx',
    "Micronesia (Federated States of)": 'fm',
    "Moldova (Republic of)": 'md',
    "Monaco (Principality of)": 'mc',
    "Mongolia": 'mn',
    "Montenegro": 'me',
    "Montserrat - United Kingdom of Great Britain and Northern Ireland": 'ms',
    "Morocco (Kingdom of)": 'ma',
    "Mozambique (Republic of)": 'mz',
    "Myanmar (Union of)": 'mm',
    "Namibia (Republic of)": 'na',
    "Nauru (Republic of)": 'nr',
    "Nepal (Federal Democratic Republic of)": 'np',
    "Netherlands (Kingdom of the)": 'nl',
    "New Caledonia - France": 'nc',
    "New Zealand": 'nz',
    "Nicaragua": 'ni',
    "Niger (Republic of the)": 'ne',
    "Nigeria (Federal Republic of)": 'ng',
    "Niue - New Zealand": 'nu',
    "Northern Mariana Islands (Commonwealth of the) - United States of America": 'mp',
    "Norway": 'no',
    "Oman (Sultanate of)": 'om',
    "Pakistan (Islamic Republic of)": 'pk',
    "Palau (Republic of)": 'pw',
    "Panama (Republic of)": 'pa',
    "Papua New Guinea": 'pg',
    "Paraguay (Republic of)": 'py',
    "Peru": 'pe',
    "Philippines (Republic of the)": 'ph',
    "Pitcairn Island - United Kingdom of Great Britain and Northern Ireland": 'pn',
    "Poland (Republic of)": 'pl',
    "Portugal": 'pt',
    "Puerto Rico - United States of America": 'pr',
    "Qatar (State of)": 'qa',
    "Reunion (French Department of) - France": 're',
    "Romania": 'ro',
    "Russian Federation": 'ru',
    "Rwanda (Republic of)": 'rw',
    "Saint Helena - United Kingdom of Great Britain and Northern Ireland": 'sh',
    "Saint Kitts and Nevis (Federation of)": 'kn',
    "Saint Lucia": 'lc',
    "Saint Paul and Amsterdam Islands - France": 'tf',
    "Saint Pierre and Miquelon (Territorial Collectivity of) - France": 'pm',
    "Saint Vincent and the Grenadines": 'vc',
    "Samoa (Independent State of)": 'ws',
    "San Marino (Republic of)": 'sm',
    "Sao Tome and Principe (Democratic Republic of)": 'st',
    "Saudi Arabia (Kingdom of)": 'sa',
    "Senegal (Republic of)": 'sn',
    "Serbia (Republic of)": 'rs',
    "Seychelles (Republic of)": 'sc',
    "Sierra Leone": 'sl',
    "Singapore (Republic of)": 'sg',
    "Slovak Republic": 'sk',
    "Slovenia (Republic of)": 'si',
    "Solomon Islands": 'sb',
    "Somalia (Federal Republic of)": 'so',
    "South Africa (Republic of)": 'za',
    "South Sudan (Republic of)": 'ss',
    "Spain": 'es',
    "Sri Lanka (Democratic Socialist Republic of)": 'lk',
    "State of Palestine (In accordance with Resolution 99 Rev. Guadalajara, 2010)": 'ps',
    "Sudan (Republic of the)": 'sd',
    "Suriname (Republic of)": 'sr',
    "Swaziland (Kingdom of)": 'sz',
    "Sweden": 'se',
    "Switzerland (Confederation of)": 'ch',
    "Syrian Arab Republic": 'sy',
    "Taiwan (Province of China) - China (People's Republic of)": 'tw',
    "Tajikistan (Republic of)": 'tj',
    "Tanzania (United Republic of)": 'tz',
    "Thailand": 'th',
    "The Former Yugoslav Republic of Macedonia": 'mk',
    "Togolese Republic": 'tg',
    "Tonga (Kingdom of)": 'to',
    "Trinidad and Tobago": 'tt',
    "Tunisia": 'tn',
    "Turkey": 'tr',
    "Turkmenistan": 'tm',
    "Turks and Caicos Islands - United Kingdom of Great Britain and Northern Ireland": 'tc',
    "Tuvalu": 'tv',
    "Uganda (Republic of)": 'ug',
    "Ukraine": 'ua',
    "United Arab Emirates": 'ae',
    "United Kingdom of Great Britain and Northern Ireland": 'gb',
    "United States Virgin Islands - United States of America": 'vi',
    "United States of America": 'us',
    "Uruguay (Eastern Republic of)": 'uy',
    "Uzbekistan (Republic of)": 'uz',
    "Vanuatu (Republic of)": 'vu',
    "Vatican City State": 'va',
    "Venezuela (Bolivarian Republic of)": 've',
    "Viet Nam (Socialist Republic of)": 'vn',
    "Wallis and Futuna Islands - France": 'wf',
    "Yemen (Republic of)": 'ye',
    "Zambia (Republic of)": 'zm',
    "Zimbabwe (Republic of)": 'zw'
}

def itu_to_iso(long_name):
    try:
        return iso_2alpha[long_name]
    except:
        return 'unknown'

if __name__=='__main__':
    codes = mmsi_codes()
    print codes
    #codes = mmsi_codes('mid.html')
    #for code in codes:
    #    print ('%s,"%s"' % (code,codes[code]))