import json,re,time
from datetime import date,timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup
BASE='https://www.mgm.gov.tr/sondurum/toplam-yagis.aspx'
OUT=Path('data.json')
H={'User-Agent':'Mozilla/5.0 MGM-Yagis-Arsivi/1.0'}
def num(s):
 s=s.replace('\xa0',' ').replace(' ','');m=re.search(r'-?\d+(?:[,.]\d+)?',s)
 return None if not m else float(m.group(0).replace(',','.'))
def fetch(d):
 r=requests.get(BASE+'?gun='+d.strftime('%d.%m.%Y')+'&t=t',headers=H,timeout=30);r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
 for tr in s.find_all('tr'):
  c=tr.find_all(['td','th'])
  if len(c)<2: continue
  name=c[0].get_text(' ',strip=True);mm=num(c[-1].get_text(' ',strip=True))
  if not name or mm is None or mm<0 or mm>2000 or ',' not in name: continue
  p=[x.strip() for x in name.split(',')];province=p[0];station=p[-1]
  out.append({'date':d.isoformat(),'province':province,'station':station,'mm':round(mm,1)})
 return list({(x['date'],x['province'],x['station']):x for x in out}.values())
def main():
 old=json.loads(OUT.read_text(encoding='utf8')) if OUT.exists() else [];db={(x['date'],x['province'],x['station']):x for x in old};today=date.today()
 for n in range(4):
  d=today-timedelta(days=n)
  try:
   rows=fetch(d);print(d,len(rows))
   for x in rows:db[(x['date'],x['province'],x['station'])]=x
  except Exception as e: print('FAILED',d,e)
  time.sleep(1)
 data=sorted(db.values(),key=lambda x:(x['date'],x['province'],x['station']));OUT.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8');print('TOTAL',len(data))
if __name__=='__main__':main()
