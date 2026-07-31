# PICO - <부재목>
<img width="1920" height="1080" alt="mockup" src="https://github.com/user-attachments/assets/5504c112-b393-403c-8636-f297fa7e0fad" />

> <한줄 설명>

---

## 핵심 기능(추가해 나가면 됨)

<table align="center" style="border-collapse: collapse; width: 100%; max-width: 1200px; margin: 20px auto; table-layout: fixed;">
  <tr>
    <td align="center" style="width: 50%; padding: 10px;">
      // 사진
      <p><strong>기능 명</strong></p>
    </td>
  </tr>
</table>

---

## 기술 스택

| 영역 | 선택 |
|---|---|
| 백엔드 | 백엔드 스택 |
| 인프라 | 인프라 스택 |
| DB | DB 스택 |
| 프론트엔드 | 프론트 스택 |
//추가 가능

## 아키텍처

```
System Arichtecture, LangGraph Arichitecture 간단 설명이랑 사진
```

---

## 시작하기(현재 구조에 맞게 수정)

### 사전 준비
- Python 3.12+
- Node.js (프론트엔드 빌드용)
- [RTZR](https://developers.rtzr.ai) 계정의 `client_id` / `client_secret`

### 실행 방법

```bash
git clone <repo-url>
cd mori

./setup.sh                # Python venv 생성 + 의존성 설치 + 프론트엔드 빌드

cp .env.example .env      # RTZR_CLIENT_ID / RTZR_CLIENT_SECRET 값 채우기
```
`.env`에 아래 값을 채워주세요.

```
RTZR_CLIENT_ID=
RTZR_CLIENT_SECRET=
```
[RTZR 개발자 콘솔](https://developers.rtzr.ai)에서 회원가입 후 앱을 생성하면 `client_id`/`client_secret`을 발급받을 수 있습니다.

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload
```

브라우저에서 `http://localhost:8000` 접속.


---

## 프로젝트 구조(수정해야함. 현재 구조에 맞게)

```
mori/
├── setup.sh
├── .env.example
├── requirements.txt
├── emotion_keywords.json      # 감정 카테고리별 키워드 정의
├── backend/
│   ├── main.py                 # FastAPI 앱, 
│   ├── rtzr_streaming_client.py
│   ├── db.py
│   ├── analysis.py            
│   └── models.py
└── frontend/
    ├── src/
    │   ├── app.ts
    │   └── audio-worklet-processor.ts
    ├── index.html
    ├── styles.css
    └── tsconfig.json
```
