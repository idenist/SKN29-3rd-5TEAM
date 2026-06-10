#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
youth-support-data-integration-v2-package 재생성 스크립트

기존 opportunities.json에서 training 데이터를 제거한 뒤,
training_youth_high_only.json / training_youth_high_chunks.jsonl을 다시 붙여
최종 opportunities.json과 opportunity_chunks.jsonl을 생성합니다.
"""
from __future__ import annotations
import csv, json, datetime
from collections import Counter
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
PROC=BASE/'data'/'processed'
COMMON_FIELDS=['item_id','original_id','source_name','source_category','domain','title','summary','benefit_text','target_text','region','age_min','age_max','application_period_text','application_start_date','application_end_date','program_period_text','program_start_date','program_end_date','organization','location','application_method','application_url','source_url','contact','tags','raw_text','info_score','needs_detail_check','collected_at','youth_relevance','youth_only','youth_preference','startup_stage','is_digital_training','is_job_seeker_friendly','training_type','is_open']

def load_json(path):
    with open(path, encoding='utf-8') as f: return json.load(f)

def iter_jsonl(path):
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def write_json(path,obj):
    with open(path,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)

def write_jsonl(path,rows):
    with open(path,'w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')

def present(v): return v is not None and str(v).strip()!=''
def clean_bool(v):
    if isinstance(v,bool): return v
    if v is None: return None
    s=str(v).strip().lower()
    if s=='true': return True
    if s=='false': return False
    return v

def ensure_prefix(v,prefix):
    s=str(v or '').strip()
    if not s: return prefix+'missing'
    return s if s.startswith(prefix) else prefix+s

def normalize_existing(row):
    r={k:row.get(k,'') for k in COMMON_FIELDS}
    r['item_id']=row.get('item_id') or ('policy_'+str(row.get('policy_id')) if row.get('policy_id') else '')
    r['original_id']=row.get('original_id') or row.get('policy_id') or row.get('item_id','')
    return r

def normalize_training(row):
    r={k:'' for k in COMMON_FIELDS}
    item=ensure_prefix(row.get('item_id'),'training_')
    r.update({
        'item_id':item,'original_id':row.get('original_id') or row.get('item_id') or item,
        'source_name':row.get('source_name') or '고용24/HRD','source_category':'training','domain':row.get('domain') or 'education',
        'title':row.get('title',''),'summary':row.get('summary',''),'benefit_text':row.get('benefit_text',''),'target_text':row.get('target_text',''),'region':row.get('region',''),
        'age_min':row.get('age_min',''),'age_max':row.get('age_max',''),'application_period_text':row.get('application_period_text',''),'application_start_date':row.get('application_start_date',''),'application_end_date':row.get('application_end_date',''),
        'program_period_text':row.get('program_period_text',''),'program_start_date':row.get('program_start_date',''),'program_end_date':row.get('program_end_date',''),
        'organization':row.get('organization',''),'location':row.get('location',''),'application_method':row.get('application_method',''),'application_url':row.get('application_url',''),'source_url':row.get('source_url',''),'contact':row.get('contact',''),
        'tags':row.get('tags',''),'raw_text':row.get('raw_text',''),'info_score':row.get('info_score',''),'needs_detail_check':clean_bool(row.get('needs_detail_check')),'collected_at':row.get('collected_at',''),
        'youth_relevance':'high','youth_only':row.get('youth_only',''),'youth_preference':row.get('youth_preference',''),'startup_stage':'','is_digital_training':clean_bool(row.get('is_digital_training')),
        'is_job_seeker_friendly':clean_bool(row.get('is_job_seeker_friendly')),'training_type':row.get('training_type',''),'is_open':clean_bool(row.get('is_open'))})
    return r

def normalize_training_chunk(obj):
    iid=ensure_prefix(obj.get('item_id'),'training_')
    obj['item_id']=iid
    obj['chunk_id']=obj.get('chunk_id') or f'{iid}::search_profile'
    if not obj['chunk_id'].startswith(iid): obj['chunk_id']=f'{iid}::'+obj['chunk_id'].split('::')[-1]
    obj['source_category']='training'; obj['domain']=obj.get('domain') or 'education'
    md=obj.get('metadata') or {}; md.update({'source_category':'training','domain':obj['domain'],'title':obj.get('title','')})
    obj['metadata']=md
    return obj

def main():
    base_opps=load_json(PROC/'opportunities.json')
    training=load_json(PROC/'training_youth_high_only.json')
    existing=[normalize_existing(r) for r in base_opps if r.get('source_category')!='training']
    train=[normalize_training(r) for r in training]
    non_high=[r for r in train if str(r.get('youth_relevance','')).lower()!='high']
    if non_high: raise RuntimeError(f'HRD non-high rows found: {len(non_high)}')
    opps=[]; seen=set(); dup=0
    for r in existing+train:
        iid=r.get('item_id')
        if iid in seen: dup+=1; continue
        seen.add(iid); opps.append(r)
    chunks=[c for c in iter_jsonl(PROC/'opportunity_chunks.jsonl') if c.get('source_category')!='training']
    chunks += [normalize_training_chunk(c) for c in iter_jsonl(PROC/'training_youth_high_chunks.jsonl')]
    final_chunks=[]; seen=set()
    for c in chunks:
        cid=c.get('chunk_id') or c.get('item_id','')+'::chunk'
        if cid in seen: continue
        seen.add(cid); final_chunks.append(c)
    write_json(PROC/'opportunities.json', opps)
    write_jsonl(PROC/'opportunity_chunks.jsonl', final_chunks)
    cat=Counter(r['source_category'] for r in opps); chunk_cat=Counter(c.get('source_category') for c in final_chunks)
    rows=[]
    for source in sorted(cat):
        rs=[r for r in opps if r['source_category']==source]
        scores=[]
        for r in rs:
            try: scores.append(float(r.get('info_score') or 0))
            except Exception: pass
        rows.append({'source_category':source,'source_name':next((r.get('source_name','') for r in rs if r.get('source_name')),''),'row_count':len(rs),'chunk_count':chunk_cat.get(source,0),'application_url_count':sum(present(r.get('application_url')) for r in rs),'source_url_count':sum(present(r.get('source_url')) for r in rs),'needs_detail_check_count':sum(str(r.get('needs_detail_check')).lower()=='true' or r.get('needs_detail_check') is True for r in rs),'info_score_avg':round(sum(scores)/len(scores),2) if scores else ''})
    with open(PROC/'integration_summary.csv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    fields=['title','summary','target_text','benefit_text','region','application_period_text','program_period_text','organization','application_url','source_url','raw_text']
    cover=[]
    for source in sorted(cat):
        rs=[r for r in opps if r['source_category']==source]
        for field in fields:
            cnt=sum(present(r.get(field)) for r in rs)
            cover.append({'source_category':source,'field':field,'present_count':cnt,'total_count':len(rs),'coverage_ratio':round(cnt/len(rs),4) if rs else 0})
    with open(PROC/'source_coverage_report.csv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(cover[0].keys())); w.writeheader(); w.writerows(cover)
    summary={'total_opportunities':len(opps),'policy_count':cat.get('policy',0),'startup_high_count':cat.get('startup_notice',0),'training_high_count':cat.get('training',0),'total_chunks':len(final_chunks),'source_categories':sorted(cat),'generated_at':datetime.datetime.now().isoformat(timespec='seconds'),'integration_rule':'온통청년 정책 전체 + K-Startup 청년 관련성 HIGH 창업공고 + HRD 청년 관련성 HIGH 교육·훈련 과정만 통합','excluded_data_note':'K-Startup medium/low 데이터는 청년 관련성이 명확하지 않거나 일반 기업 대상 성격이 있어 현재 서비스 통합 대상에서 제외함. HRD medium/low 데이터는 청년 취업·디지털 교육 관련성이 상대적으로 낮거나 일반 훈련 과정으로 분류되어 현재 서비스 통합 대상에서 제외함.','item_id_duplicate_count':dup}
    write_json(PROC/'preprocessing_summary.json', summary)
    print(f"완료: opportunities={len(opps):,}, chunks={len(final_chunks):,}, duplicate_skipped={dup}")
if __name__=='__main__': main()
