#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HRD/고용24 국민내일배움카드 훈련과정 청년 적합 과정 전처리 스크립트.

실행:
python scripts/preprocess_hrd_training_youth.py --input data/raw/hrd_training_api/hrd_training_raw_items.json --output-dir data/processed

이 스크립트는 원본 JSON을 읽어 다음 산출물을 생성합니다.
- training_youth_classified_all.csv
- training_youth_high_only.csv
- training_youth_high_medium.csv
- training_youth_medium_reference_only.csv
- training_youth_low_reference_only.csv
- training_youth_high_only.json
- training_youth_high_chunks.jsonl
- training_youth_relevance_report.csv
- training_type_report.csv
- preprocessing_summary.json
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, re
from pathlib import Path
from collections import Counter

COMMON_COLUMNS = [
    'item_id','source_name','source_category','domain','title','summary','benefit_text','target_text','region','age_min','age_max',
    'application_period_text','application_start_date','application_end_date','program_period_text','program_start_date','program_end_date',
    'organization','location','application_method','application_url','source_url','contact','tags','raw_text','youth_relevance',
    'youth_relevance_reason','training_type','is_digital_training','is_job_seeker_friendly','is_open','info_score','needs_detail_check','collected_at'
]
DIRECT_YOUTH = ['청년','미취업청년','청년구직자','대학생','졸업예정자','사회초년생','청년층','청년특화']
JOB_SEEKER = ['취업준비생','미취업자','미취업','구직자','실업자','취업준비','취업연계','채용연계','양성과정','취업과정']
DIGITAL = ['K-Digital','KDT','디지털 인재','AI','인공지능','데이터 분석','데이터','빅데이터','파이썬','Python','자바','Java','웹개발','앱개발','프론트엔드','백엔드','클라우드','정보보안','UX/UI','UI/UX','디지털마케팅','개발자','코딩','프로그래밍','SW','소프트웨어','머신러닝','딥러닝','풀스택','리액트','React','스프링','Spring','SQL','DB','데이터베이스','웹디자인']
LOW_KEYS = ['사업주훈련','기업 단체훈련','법정의무교육','관리자 과정','임원 교육','중장년','시니어','고령자','재직자 향상','산업안전관리자','사업주','컨소시엄','근로자 직무능력향상']
MEDIUM_KEYS = ['국민내일배움카드','일반','재직자','자격증','컴퓨터활용능력','컴활','전산회계','회계','세무','바리스타','조리','요양보호사','전기기능사','용접','사무자동화','직업훈련','간호조무사','미용','네일','피부','제과','제빵','기능사']
TYPE_RULES = [
    ('데이터/AI', ['AI','인공지능','데이터','빅데이터','머신러닝','딥러닝','분석','Python','파이썬','SQL']),
    ('개발', ['개발','자바','Java','웹개발','앱개발','프론트엔드','백엔드','풀스택','리액트','React','스프링','Spring','코딩','프로그래밍','소프트웨어','SW']),
    ('IT/디지털', ['K-Digital','KDT','디지털','클라우드','정보보안','보안','네트워크','컴퓨터','OA','ITQ','컴활']),
    ('디자인/UX', ['UX','UI','디자인','그래픽','영상','편집','웹디자인','포토샵','일러스트']),
    ('사무/회계', ['회계','세무','전산회계','전산세무','ERP','사무','엑셀','컴퓨터활용능력','컴활']),
    ('보건/복지', ['요양보호사','간호','보건','복지','사회복지','병원','의료']),
    ('조리/식음료', ['조리','한식','양식','일식','중식','제과','제빵','바리스타','커피','식음료']),
    ('제조/기술', ['용접','전기','기계','자동차','건축','토목','설비','CAD','캐드','품질','산업안전']),
    ('서비스', ['미용','헤어','네일','피부','서비스','관광','호텔','항공','물류','유통']),
]

def safe(v): return '' if v is None else str(v).strip()
def pick(row, keys):
    lower = {str(k).lower(): k for k in row.keys()}
    for k in keys:
        if k in row and safe(row.get(k)): return safe(row.get(k))
        lk = k.lower()
        if lk in lower and safe(row.get(lower[lk])): return safe(row.get(lower[lk]))
    return ''
def has_any(text, keys):
    low = text.lower()
    return [k for k in keys if k.lower() in low]
def parse_date(s):
    m = re.search(r'(20\d{2})[-./]?(\d{2})[-./]?(\d{2})', safe(s))
    if not m: return ''
    try: return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError: return ''
def bool_text(x): return 'true' if x else 'false'
def classify_type(text):
    for typ, keys in TYPE_RULES:
        if has_any(text, keys): return typ
    return '기타'
def classify(text):
    direct = has_any(text, DIRECT_YOUTH)
    digital = has_any(text, DIGITAL)
    job = has_any(text, JOB_SEEKER)
    low = has_any(text, LOW_KEYS)
    medium = has_any(text, MEDIUM_KEYS)
    strong_job = bool(job and has_any(text, ['취업','양성과정','채용','실무','직무','훈련','과정']))
    if direct: return 'high', '청년/대학생/졸업예정자 등 청년 직접 키워드 포함'
    if digital: return 'high', '디지털·IT·AI·데이터·개발 관련 청년 취업 친화 과정'
    if strong_job: return 'high', '구직자/미취업자/취업준비 대상이며 취업훈련 성격이 강함'
    if low and not (direct or digital or strong_job): return 'low', '사업주/기업/중장년/법정교육 등 청년 지원 서비스 관련성 낮음'
    if medium or job: return 'medium', '일반 내일배움카드/구직자/자격증/직업훈련 과정으로 청년도 수강 가능하나 청년 특화 근거는 약함'
    return 'medium', '청년 특화 근거는 부족하지만 일반 훈련과정으로 참고 가능'
def make_item_id(row):
    parts = [pick(row,['title','trprNm','tracseNm','courseName']), pick(row,['subTitle','trainstCstmrNm','instNm']), pick(row,['traStartDate','trSttDt']), pick(row,['traEndDate','trEndDt']), pick(row,['titleLink','detailUrl','link']), pick(row,['trprId','tracseId'])]
    return 'training_' + hashlib.md5('|'.join(parts).encode('utf-8')).hexdigest()[:12]
def normalize(row):
    title=pick(row,['title','trprNm','tracseNm','courseName','훈련과정명']); org=pick(row,['subTitle','trainstCstmrNm','instNm','훈련기관명']); region=pick(row,['address','addr1','traArea1','region','지역']); target=pick(row,['trainTarget','trget','target','훈련대상']); start_raw=pick(row,['traStartDate','trSttDt','trainStartDate','훈련시작일']); end_raw=pick(row,['traEndDate','trEndDt','trainEndDate','훈련종료일']); source_url=pick(row,['titleLink','detailUrl','link','url','상세URL']); contact=pick(row,['telNo','tel','전화번호']); cost=pick(row,['courseMan','realMan','훈련비']); cert=pick(row,['certificate']); ncs=pick(row,['ncsCd']); title_icon=pick(row,['titleIcon']); contents=pick(row,['contents']); period=' ~ '.join([x for x in [start_raw,end_raw] if x])
    raw_text='\n'.join([x for x in [f'훈련과정명: {title}' if title else '', f'훈련기관: {org}' if org else '', f'훈련대상: {target}' if target else '', f'지역: {region}' if region else '', f'훈련기간: {period}' if period else '', f'훈련비/지원정보: {cost}' if cost else '', f'자격증: {cert}' if cert else '', f'NCS코드: {ncs}' if ncs else '', f'상세URL: {source_url}' if source_url else '', contents, title_icon] if x])
    text=' '.join([title, org, target, region, cost, cert, ncs, contents, title_icon]); rel, reason = classify(text); typ = classify_type(text); is_dig=bool(has_any(text,DIGITAL)); is_job=bool(has_any(text,JOB_SEEKER)); p_start=parse_date(start_raw); p_end=parse_date(end_raw); is_open='확인필요'
    if p_end:
        try: is_open='true' if dt.date.fromisoformat(p_end) >= dt.date.today() else 'false'
        except Exception: is_open='확인필요'
    missing=sum(1 for x in [title, org, region, period, source_url, raw_text] if not x); info=max(0,100-missing*12); needs=missing>=2 or not source_url; summary=' / '.join([x for x in [title,org,target,region,period,typ] if x]); tags=','.join([x for x in ['교육','훈련','국민내일배움카드',typ,region,'디지털' if is_dig else '','취업친화' if is_job else ''] if x])
    return {'item_id':make_item_id(row),'source_name':'고용24/HRD','source_category':'training','domain':'education','title':title,'summary':summary,'benefit_text':cost,'target_text':target,'region':region,'age_min':'','age_max':'','application_period_text':'','application_start_date':'','application_end_date':'','program_period_text':period,'program_start_date':p_start,'program_end_date':p_end,'organization':org,'location':region,'application_method':'','application_url':'','source_url':source_url,'contact':contact,'tags':tags,'raw_text':raw_text,'youth_relevance':rel,'youth_relevance_reason':reason,'training_type':typ,'is_digital_training':bool_text(is_dig),'is_job_seeker_friendly':bool_text(is_job),'is_open':is_open,'info_score':info,'needs_detail_check':bool_text(needs),'collected_at':dt.date.today().isoformat()}
def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=COMMON_COLUMNS, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def write_json(path, rows): path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
def write_jsonl(path, rows):
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            content='\n'.join([x for x in [f"훈련과정명: {r['title']}", f"훈련기관: {r['organization']}", f"훈련유형: {r['training_type']}", f"훈련대상: {r['target_text']}", f"지역: {r['region']}", f"훈련기간: {r['program_period_text']}", f"청년 관련성: {r['youth_relevance']} ({r['youth_relevance_reason']})", f"상세URL: {r['source_url']}", r['raw_text']] if x and not x.endswith(': ')])
            obj={'chunk_id':f"{r['item_id']}::search_profile",'item_id':r['item_id'],'source_category':'training','domain':'education','title':r['title'],'content':content,'metadata':{'youth_relevance':r['youth_relevance'],'training_type':r['training_type'],'is_digital_training':r['is_digital_training'],'is_job_seeker_friendly':r['is_job_seeker_friendly'],'is_open':r['is_open'],'region':r['region'],'organization':r['organization'],'program_start_date':r['program_start_date'],'program_end_date':r['program_end_date'],'source_url':r['source_url'],'application_url':r['application_url']}}
            f.write(json.dumps(obj, ensure_ascii=False)+'\n')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--input', default='data/raw/hrd_training_api/hrd_training_raw_items.json'); p.add_argument('--output-dir', default='data/processed'); args=p.parse_args(); out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    raw=json.load(open(args.input, encoding='utf-8')); normalized=[normalize(r) for r in raw]; seen={}; dup=0
    for r in normalized:
        if r['item_id'] in seen: dup+=1
        else: seen[r['item_id']]=r
    rows=list(seen.values()); high=[r for r in rows if r['youth_relevance']=='high']; medium=[r for r in rows if r['youth_relevance']=='medium']; low=[r for r in rows if r['youth_relevance']=='low']; high_medium=[r for r in rows if r['youth_relevance'] in ('high','medium')]
    for name, subset in [('training_youth_classified_all.csv',rows),('training_youth_high_only.csv',high),('training_youth_high_medium.csv',high_medium),('training_youth_medium_reference_only.csv',medium),('training_youth_low_reference_only.csv',low)]: write_csv(out/name,subset)
    write_json(out/'training_youth_high_only.json', high); write_jsonl(out/'training_youth_high_chunks.jsonl', high)
    n=len(rows); report=[{'youth_relevance':label,'count':len(subset),'ratio':round(len(subset)/n,6) if n else 0} for label,subset in [('high',high),('medium',medium),('low',low)]]
    with open(out/'training_youth_relevance_report.csv','w',encoding='utf-8-sig',newline='') as f: w=csv.DictWriter(f,fieldnames=['youth_relevance','count','ratio']); w.writeheader(); w.writerows(report)
    tc=Counter(r['training_type'] for r in rows)
    with open(out/'training_type_report.csv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['training_type','count','ratio']); w.writeheader()
        for typ,cnt in tc.most_common(): w.writerow({'training_type':typ,'count':cnt,'ratio':round(cnt/n,6) if n else 0})
    summary={'generated_at':dt.datetime.now().isoformat(timespec='seconds'),'source_name':'고용24/HRD 국민내일배움카드 훈련과정','raw_input_count':len(raw),'deduplicated_count':len(rows),'duplicate_item_id_count':dup,'high_count':len(high),'medium_count':len(medium),'low_count':len(low),'high_ratio':round(len(high)/n,6) if n else 0,'note':'이번 작업은 HRD/내일배움카드 훈련과정 정제까지만 수행하며 기존 opportunities.json과 통합하지 않습니다.'}
    (out/'preprocessing_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('전처리 완료:', summary)
if __name__ == '__main__': main()
