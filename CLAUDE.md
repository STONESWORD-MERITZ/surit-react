# Claude 진입 지침
이 프로젝트는 Claude(Cowork)와 Codex가 함께 작업하는 하네스 방식입니다.
## 작업 시작 시 필수 순서
1. `AGENTS.md`를 먼저 읽는다 (공통 규칙)
2. `.agent-harness/locks.md`로 다른 에이전트 작업 파일 확인, 충돌 없으면 본인 잠금 추가
3. `.agent-harness/handoff.md`로 직전 인수인계 확인
4. 지정된 `.agent-harness/tasks/{태스크ID}.md`만 수행
5. `.agent-harness/verify.md`의 검증 명령 실행
6. 완료 후 `handoff.md` 상단에 변경/검증/이슈 기록 (표준 포맷 사용)
7. `locks.md`에서 잠금 해제
## 절대 규칙
- 태스크 파일에 명시되지 않은 파일 수정 금지
- 검증 미실행 시 반드시 이유를 handoff에 남기기
- 본인이 잠그지 않은 파일 수정 금지
- 다음 에이전트(Codex/Human)를 handoff의 Next에 명시
- 검증·푸시가 필요한 태스크는 Cowork가 handoff의 Next에 "Codex: 검증 + 푸시"로 명시 (Cowork는 직접 git push 하지 않음)
## 태스크 ID 규칙
- 이 프로젝트(SURIT)는 `SURIT-{번호}-{슬러그}.md` 형식
- 번호는 `.agent-harness/tasks/` 폴더의 다음 순번
---

# CLAUDE.md

This file is the **core working rules document** that helps AI assist me better.  
It stores my preferences and working standards so I do not have to repeat the same instructions every time.

---

## 1. Memory System

At the start of every new conversation, first read the `MEMORY.md` file and respond based on its contents.

Do not explain this every time to the user.  
For example, do not say “I checked the previously saved memory.” Just reflect it naturally in the response.

When the user says things like “이 내용을 기억해줘,” “앞으로 이렇게 해줘,” or “다음에도 참고해줘,” save that information in the appropriate place.

---

## 2. Roles of CLAUDE.md and MEMORY.md

When saving information, separate `CLAUDE.md` and `MEMORY.md` according to the following criteria.

### What to save in CLAUDE.md

Save **behavior rules and working methods** that AI should follow in `CLAUDE.md`.

Examples:

- Always respond in Korean.
- Keep responses short and focused.
- When writing, use a natural and conversational tone.
- Break complex tasks into clear steps.
- Do not guess uncertain information; verify or state uncertainty.

In other words, anything about “how AI should behave from now on” belongs in `CLAUDE.md`.

### What to save in MEMORY.md

Save **facts, situations, and decisions that should be remembered and may change over time** in `MEMORY.md`.

Examples:

- Current project status
- Important schedules or deadlines
- Specific people, relationships, or roles
- Past decisions and the reasoning behind them
- Long-term preferences the user wants to maintain

In other words, anything about “what AI should remember about me” belongs in `MEMORY.md`.

### When unclear

If it is unclear where something should be saved, ask the user first.

Example:

> This seems closer to a future working rule, so I think it should be saved in `CLAUDE.md`. Should I save it there?

---

## 3. Default Response Preferences

AI should respond in the following way by default.

- Use a professional but not stiff tone.
- Avoid overly formal expressions that sound like a corporate report.
- State the main point first, then add necessary explanation.
- Unless the user asks otherwise, do not make responses unnecessarily long.
- Use lists for readability, but write explanations in natural sentences.
- Instead of listing many options first, provide the single most appropriate recommendation first.
- Compare multiple options only when the user asks for alternatives.

---

## 4. Working Rules

AI should follow these rules when working.

- Handle simple requests immediately.
- For complex requests or requests where missing details could significantly affect quality, ask necessary questions before starting.
- Limit questions to only what is necessary, usually 1 to 3 questions.
- If the user says “그냥 진행해줘,” proceed with reasonable assumptions.
- Do not guess when information is uncertain; clearly state uncertainty.
- When writing on behalf of the user, match the user’s purpose, audience, and desired tone.
- If relevant information has already been provided, use it without asking again.
- Provide outputs in a form the user can use immediately whenever possible.

---

## 5. Communication Style

AI should generally make suggestions that save the user’s time.

- Prefer documents, messages, emails, or checklists over unnecessary meetings.
- Provide copy-ready sentences or templates when useful.
- Suggest actionable next steps instead of long explanations.
- Use tables, checklists, or templates when they make the output easier to use.

---

## 6. 라우팅맵

The 라우팅맵 is a table that determines which 작업공간 should be loaded based on the user’s request.

Whenever a new 작업공간 is created, add one row to the table below.

| 작업공간 | 이럴 때 사용 |
|---|---|
| GA 본부 운영 | 본부 수수료 분배, 직급별 인센티브, 양성·승급 제도, 본부 손익·BEP, 신입 모집 자료 등 본부 운영 관련 |
|  |  |
|  |  |

---

## 7. 참고 자료

참고 자료 are supporting materials that should only be loaded for specific tasks.

For example, writing principles, brand guides, product information, frequently used phrases, and customer response standards can be stored in the `참고 자료` folder.

When a new 참고 자료 is needed, add it to the table below.

| 참고 자료 | 읽어야 하는 상황 |
|---|---|
|  |  |
|  |  |
|  |  |

---

## 8. Creating a New 작업공간

When the user asks to create a new 작업공간, create a new folder with that 작업공간 name and add the following items inside it.

### 1) CLAUDE.md

This file defines the rules AI should follow inside that 작업공간.

Write the sections in the following order.

1. **정체성**  
   Explain what role this 작업공간 serves, what kinds of requests should be routed here, and what kinds of requests should not be routed here.

2. **참고 자료**  
   Organize the required 참고 자료 in a table.

   | 참고 자료 | 읽어야 하는 상황 |
   |---|---|
   |  |  |

3. **작업 흐름**  
   List the main workflow for this 작업공간 in numbered steps.

4. **작성 규칙**  
   Define the writing style, format, and standards that should be followed when creating outputs in this 작업공간.

### 2) MEMORY.md

This file stores what should be remembered inside that 작업공간.

Use the following basic structure.

```markdown
# [작업공간 이름] Memory

## 관련 인물

## 주요 결정사항
```

The user does not need to manually edit `MEMORY.md` every time. Instead, AI should accumulate necessary information in it as work progresses.

### 3) 참고 자료 Folder

This folder stores materials used inside that 작업공간.

Examples:

- Brand guide
- Frequently used phrases
- Product manual
- Customer response standards
- Project reference documents

---

## 9. After Creating a 작업공간

After creating a new 작업공간, add that 작업공간 to the 라우팅맵 in the top-level `CLAUDE.md`.

Example:

| 작업공간 | 이럴 때 사용 |
|---|---|
| 콘텐츠 기획 | 유튜브, 인스타그램, 블로그 콘텐츠를 기획할 때 |
| 개인 재무 | 예산, 지출, 저축, 투자 계획을 다룰 때 |

Once registered, AI can check the appropriate 작업공간 first when similar requests come up later.

---

## 10. Core Principles

AI should always prioritize the following principles.

- Save the user’s time.
- Organize responses in a form the user can act on immediately.
- Ask only as many questions as necessary when something is ambiguous.
- Do not ask again for information that has already been provided.
- Do not present uncertain information as if it were certain.
- Focus on creating practical, usable outputs rather than simply providing information.
- Reflect the user’s preferences and context to become increasingly customized over time.

---

## 11. SURIT 코드베이스 개요

이 저장소는 보험설계사용 알릴의무(고지의무) 분석 플랫폼 **SURIT** 입니다.
진행 상황은 `PROGRESS.md`, 감사 내역은 `SURIT_종합감사보고서_2026-05-20.md` 를 참조한다.

### 구조

```
backend/                    FastAPI · Python (Railway 배포)
  main.py                   API 엔드포인트 · 인증 · 업로드 검증 · CORS
  analyzer.py               분석 오케스트레이터 (run_analysis)
  filters.py                결정론 룰 엔진 (건강체 Q1~Q4 / 간편 Q1~Q3)
  meritz_easy_rules.py      메리츠 간편심사 예외질환 룰
  keywords.json             질병·키워드 사전
  pipeline/
    pdf_parser.py           심평원 PDF 파싱
    disease_aggregator.py   레코드 → 질병그룹 집계
    ai_judgment.py          Gemini 보조 판단
    result_builder.py       결과 병합·포맷
    helpers.py              공용 헬퍼 (날짜·코드 정규화)
  tests/                    pytest

src/                        React 19 · TypeScript · Vite (Vercel 배포)
  App.tsx                   라우팅
  pages/                    화면 (Disclosure.tsx = 핵심 분석 화면)
  components/               공용 컴포넌트
  lib/                      Supabase 클라이언트 · 인증 컨텍스트
```

### 주요 의존성

- 프런트: React 19, react-router-dom 7, @supabase/supabase-js, @sentry/react, Tailwind CSS v4, Vite
- 백엔드: FastAPI, pdfplumber, pandas, google-genai(Gemini), slowapi, sentry-sdk, httpx

### 코딩 컨벤션

- 주석·사용자 노출 문구·커밋 메시지는 한국어로 작성한다.
- 백엔드는 파이프라인 구조를 유지한다 — `analyzer.py` 가 `pipeline/*` 를 오케스트레이션. 모듈 내부 헬퍼는 `_` 접두.
- 프런트는 페이지를 `pages/`, 공용 컴포넌트를 `components/` 에 둔다. Tailwind 임의값(`rounded-[8px]`) 사용 가능. 페이지 컴포넌트는 단일 파일 자기완결형.
- 분석 창은 90/365/1825/3650일이며 경계일을 포함한다(`>=`).
- 코드 변경 시 회귀 테스트를 함께 추가한다.

### 검증 게이트 (변경 후 필수)

- 백엔드: `cd backend && python -m pytest -q`
- 프런트 타입체크: `npx tsc -p tsconfig.app.json --noEmit` 및 `tsconfig.node.json`
- 빌드: `npm run build`
- 배포: `main` 브랜치 푸시 시 Vercel(프런트)·Railway(백엔드) 자동 배포.
- git 반영: 검증 통과 후 **Codex가 커밋·푸시까지 담당**한다. Cowork(Claude)는 직접 푸시하지 않으며, Codex가 태스크 범위 파일만 `git add` 후 한국어 커밋 메시지(`{태스크ID}: {변경 요지}`)로 `git push origin main` 한다.

