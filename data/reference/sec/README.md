# SEC reference snapshots

SEC ticker–CIK와 submissions 원본 및 정규화 산출물은 로컬 manifest로
관리한다. 현재 ticker 연결만으로 과거 식별을 확정하지 않는다.

Company Facts는 accession number를 submissions의 `acceptanceDateTime`에
연결한 뒤에만 point-in-time 입력으로 사용한다. 연결되지 않은 관측값,
현재 ticker만으로 추정한 과거 CIK, 문서를 검토하지 않은 합병 후보는
검증 입력에서 제외한다.

Form 4 원문 snapshot은 SEC submissions의 accession을 후보로만 사용하고,
XML 본문의 `issuerCik` 일치를 다시 확인한다. reporting owner로 인해
issuer가 다른 문서는 rejection 원장에 남기고 종목 거래에서 제외한다.
원문 파일은 SHA-256 내용 주소로 저장하며 가격 결과와 결합하지 않는다.
