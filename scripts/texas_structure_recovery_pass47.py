
#!/usr/bin/env python3
"""Pass 47: dated Texas whole-school/strand evidence, without exposure imputation."""
import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

URL = {
 'SA': 'https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/5576/Saisd/8dcc7b27-f611-4f66-b639-df28ed4f2368/SAISD-Dual-Language-Handbook-.docx.pdf?disposition=inline',
 'FW': 'https://resources.finalsite.net/images/v1717011774/fwisdorg/c4m04t2a5sxkxb8kdx2k/Two-Way_Informational_Flyer_2-20-18.pdf',
 'DAL': 'https://thehub.dallasisd.org/dallas-isd-news-archives/dallas-isd-news-archives-post-page/~board/dallas-isd-news-archives/post/seven-additional-schools-to-offer-two-way-dual-language-program-this-school-year',
 'AUSTIN': 'https://go.boarddocs.com/tx/austinisd/Board.nsf/files/BXV8M91EEF9E/%24file/Attachment%202%20-%20Dual%20Language%20Programs%20by%20Elementary%20Campus%202020-21.pdf',
 'RR': 'https://www.boarddocs.com/tx/rrisd/Board.nsf/files/AQBK2U4FCE00/%24file/H2.DL%20Board%20Presentation%208-17-17%20%281%29.pdf',
 'WHARTON': 'https://wharton.houstonisd.org/academics-programs/academic-offerings',
 'HELMS': 'https://helms.houstonisd.org/about-us/school-history',
 'LOVE': 'https://love.houstonisd.org/academics-programs',
 'BROWNING': 'https://browning.houstonisd.org/about-us',
 'MARK_WHITE': 'https://mwhite.houstonisd.org/academics-programs/dual-language-immersion-programs',
 'SPRING': 'https://news.springisd.org/2020/04/pre-k-and-kindergarten-online-registration-for-2020-21-school-year-opens-april-27/',
 'BAMMEL': 'https://news.springisd.org/2021/05/dual-language-program-to-anchor-new-school-for-international-studies-at-bammel/',
 'SOUTH_SAN': 'https://sanantonioreport.org/south-san-isd-to-add-dual-language-programs-at-5-elementary-schools/',
}

# 2023-24 San Antonio district handbook: DL offered by grade.
# An offering does NOT establish universal participation.
SA_GRADES = dict(item.split(':') for item in '''
015907101:PK-5 015907103:PK-5 015907106:PK-5 015907107:K-8
015907110:K-5 015907112:PK-5 015907116:PK-5 015907117:PK-8
015907118:PK-7 015907121:K-5 015907123:PK-3 015907126:PK-5
015907133:PK-4 015907134:PK-5 015907135:PK-5 015907136:PK-5
015907138:PK-8 015907144:K-5 015907146:PK-4 015907147:PK-5
015907148:PK-5 015907149:K-5 015907150:K-5 015907153:PK-5
015907155:K-5 015907158:PK-5 015907160:PK-5 015907161:PK-8
015907163:PK-8 015907164:PK-5 015907165:PK-5 015907168:PK-5
015907172:PK-6 015907174:PK-5 015907175:K-8 015907176:PK-5
015907241:PK-5
'''.split())

SA_WALL = {'015907138', '015907163'}

FW_FOUNDING = '''
220905149 220905116 220905127
'''.split()

FW_ADDED = '''
220905117 220905160 220905121 220905107
220905153 220905148 220905166
'''.split()

DALL
