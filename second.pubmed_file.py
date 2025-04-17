import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time

# 翻訳ライブラリ
try:
    from googletrans import Translator
    translator = Translator()
except ImportError:
    print("googletrans がインストールされていません。翻訳はスキップされます。")
    translator = None

journals = [
    "World Psychiatry",
    "JAMA Psychiatry",
    "Lancet Psychiatry",
    "American Journal of Psychiatry",
    "Annual Review of Clinical Psychology",
    "Psychological Medicine",
    "Schizophrenia Bulletin"
]

def search_pubmed(journal, start_date, end_date, retmax=10):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    query = f'"{journal}"[Journal] AND ("{start_date}"[PDAT] : "{end_date}"[PDAT])'
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "sort": "pub+date",
        "retmode": "xml"
    }
    response = requests.get(base_url, params=params)
    try:
        tree = ET.fromstring(response.content)
    except ET.ParseError as e:
        print(f"[ERROR] XML parse error in search_pubmed for {journal}: {e}")
        return []
    id_list = [elem.text for elem in tree.findall(".//Id")]
    return id_list

def fetch_article_summary(pubmed_id):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": pubmed_id,
        "retmode": "xml"
    }
    response = requests.get(base_url, params=params)
    try:
        tree = ET.fromstring(response.content)
    except ET.ParseError as e:
        print(f"XML Parse Error for PMID {pubmed_id}: {e}")
        return "No Title", "Parse Error"
    title_elem = tree.find(".//ArticleTitle")
    abstract_elem = tree.find(".//AbstractText")
    title = title_elem.text if title_elem is not None else "No Title"
    abstract = abstract_elem.text if abstract_elem is not None else ""
    summary = abstract[:500] + ("..." if len(abstract) > 500 else "")
    return title, summary

def translate_text(text, lang="ja"):
    if not translator or not text:
        return text
    for _ in range(3):  # 最大3回リトライ
        try:
            return translator.translate(text, dest=lang).text
        except Exception as e:
            print(f"[翻訳エラー] リトライ中: {e}")
            time.sleep(1)
    return text

def save_to_file(messages, start_date, end_date):
    desktop_path = os.path.expanduser("~/Desktop")
    save_directory = os.path.join(desktop_path, "pubmed_updates")
    os.makedirs(save_directory, exist_ok=True)
    file_name = os.path.join(save_directory, f"pubmed_updates_{start_date}_{end_date}.txt")
    with open(file_name, "w", encoding="utf-8") as file:
        file.write("\n".join(messages))
    print(f"✅ ファイル保存完了: {file_name}")

def job_send_pubmed_updates():
    today = datetime.today()
    last_week = today - timedelta(days=7)
    start_date_query = last_week.strftime("%Y/%m/%d")
    end_date_query = today.strftime("%Y/%m/%d")
    start_date_file = last_week.strftime("%Y%m%d")
    end_date_file = today.strftime("%Y%m%d")
    
    messages = []
    for journal in journals:
        print(f"🔍 Checking journal: {journal}")
        pmids = search_pubmed(journal, start_date_query, end_date_query, retmax=5)
        if not pmids:
            print(f"⚠️ {journal}: 新しい論文は見つかりませんでした。")
            continue
        
        messages.append(f"◆ {journal} ◆\n")
        for pmid in pmids:
            title_en, abstract_en = fetch_article_summary(pmid)
            title_ja = translate_text(title_en)
            abstract_ja = translate_text(abstract_en)
            pubmed_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            messages.append(
                f"タイトル（英）: {title_en}\n"
                f"タイトル（和訳）: {title_ja}\n"
                f"要約（英）: {abstract_en}\n"
                f"要約（和訳）: {abstract_ja}\n"
                f"PMID: {pmid}\n"
                f"リンク: {pubmed_link}\n"
                "\n" + "-"*40 + "\n"
            )
            time.sleep(0.4)

    if messages:
        save_to_file(messages, start_date_file, end_date_file)
                # メール送信も行う
        send_email(
            subject=f"[PubMedまとめ] {start_date_file}〜{end_date_file}",
            body="\n".join(messages)
        )

    else:
        print("✅ 新着論文は見つかりませんでした。")

if __name__ == "__main__":
    job_send_pubmed_updates()

import smtplib
from email.mime.text import MIMEText
import os

def send_email(subject, body):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("✅ メール送信成功")
    except Exception as e:
        print("❌ メール送信エラー:", e)
