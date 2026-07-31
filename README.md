# PICO - AI와 함께 완성하는 서비스 기획서
<img width="1920" height="1080" alt="mockup" src="https://github.com/user-attachments/assets/22850641-1d50-491b-9b84-a1a481e08e74" />

> 아이디어 한 줄이면, 시장조사부터 MVP 로드맵까지 7단계 기획 문서를 AI와 단계별로 검토·수정하며 완성한다

---

## 핵심 기능

<table align="center" style="border-collapse: collapse; width: 100%; max-width: 1200px; margin: 20px auto; table-layout: fixed;">
  <tr>
    <td align="center" style="width: 50%; padding: 10px;">
      <img width="746" height="492" alt="image" src="https://github.com/user-attachments/assets/e6a7429a-b572-46b0-a8ee-0bacbda24f47" />
      <p><strong>질문하기</strong></p>
    </td>
    <td align="center" style="width: 50%; padding: 10px;">
      <img width="675" height="488" alt="image" src="https://github.com/user-attachments/assets/80a98cb9-ae32-4ce6-9c21-443a657bad4e" />
      <p><strong>7단계 자동 기획 파이프라인</strong></p>
    </td>
  </tr>
  <tr>
    <td align="center" style="width: 50%; padding: 10px;">
      <img width="637" height="347" alt="image" src="https://github.com/user-attachments/assets/75faa3b3-8b30-44f8-b244-e30376b3b5e1" />
      <p><strong>단계별 승인/수정/질문 리뷰</strong></p>
    </td>
    <td align="center" style="width: 50%; padding: 10px;">
      <img width="652" height="507" alt="image" src="https://github.com/user-attachments/assets/2365ac04-1e7a-44e1-9989-0cdbfabc1380" />
      <p><strong>최종 기획서 생성</strong></p>
    </td>
  </tr>
</table>

---

## 기술 스택

| 영역 | 선택 |
|---|---|
| 백엔드 | FastAPI, LangGraph, SQLAlchemy(Async) |
| LLM / 검색 | HyperCLOVA X (CLOVA Studio), Naver Search API(NCP API HUB) |
| 인프라 | GCP (Compute Engine, Load Balancing, Artifact Registry), Docker, GitHub Actions |
| DB | PostgreSQL(Supabase), Redis |
//추가 가능

## 아키텍처

## System Architecture

<p align="center">
  <img width="950" alt="System Architecture" src="https://github.com/user-attachments/assets/c42b4929-fbc6-4312-9ec9-1b8da3d4dbca" />
</p>

## LangGraph Architecture

<p align="center">
  <img width="610" alt="LangGraph Architecture" src="https://github.com/user-attachments/assets/1165b825-7afd-4be6-9552-f2bf75620407" />
</p>
---

## 시작하기

### 사전 준비
- Python 3.12 (3.14는 pydantic-core 빌드 실패로 사용 불가)
- PostgreSQL (Supabase 등)
- Redis
- [CLOVA Studio](https://clovastudio.ncloud.com) API 키
- Naver API HUB(NCP) `Client ID` / `Client Secret`

### 실행 방법

```bash
git clone <repo-url>
cd PICO-BE

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # requirements.txt + pytest/ruff 포함

cp .env.example .env      # 아래 값 채워주기
```
`.env`에 아래 값을 채워주세요.

```
CLOVA_API_KEY=
CLOVA_MODEL=HCX-005
CLOVA_API_BASE_URL=https://clovastudio.stream.ntruss.com

NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

DATABASE_URL=
JWT_SECRET_KEY=
REDIS_URL=redis://localhost:6379/0
```

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

`http://localhost:8000/api/health` 접속해서 정상 기동 확인.


---

## 프로젝트 구조

```
PICO-BE/
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── alembic/                    # DB 마이그레이션
├── deploy/
│   ├── docker-compose.yml      # 배포 VM에서 실행되는 api + redis
│   └── gcp-setup.sh            # 1회성 GCP 인프라 부트스트랩
├── app/
│   ├── main.py                 # FastAPI 앱 엔트리포인트
│   ├── api/
│   │   ├── api.py              # 라우터 등록
│   │   ├── deps.py
│   │   └── endpoints/          # auth.py, plan.py, health.py
│   ├── core/                   # config, security, sse, langfuse_client
│   ├── graph/
│   │   ├── graph.py             # LangGraph 그래프 정의
│   │   ├── nodes.py             # 노드 로직 + 단계별 분석 함수
│   │   └── state.py             # PicoState, STAGE_ORDER
│   ├── services/
│   │   ├── llm_client.py        # CLOVA 클라이언트 + 단계별 프롬프트
│   │   ├── search_client.py     # Naver 검색 클라이언트
│   │   └── draft_repository.py
│   ├── models/                  # user, draft
│   ├── schemas/                 # auth, plan
│   ├── utils/                   # citations, perf
│   └── db/                      # session, redis, base
└── tests/
```
