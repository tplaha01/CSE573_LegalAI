from app.schemas import CaseAnalysisRequest, LegalQuery


class LegalQueryBuilder:

    def build(
        self,
        request: CaseAnalysisRequest,
    ) -> LegalQuery:

        facts = request.facts.strip()
        issues = request.legal_issues.strip()

        petitioner = request.petitioner_arguments.strip()
        respondent = request.respondent_arguments.strip()

        evidence = request.evidence.strip()
        statutes = request.statutes.strip()
        question = request.question.strip()

        arguments_parts = []

        if petitioner:
            arguments_parts.append(
                f"Petitioner position: {petitioner}"
            )

        if respondent:
            arguments_parts.append(
                f"Respondent position: {respondent}"
            )

        arguments_query = " ".join(arguments_parts)

        query_parts = []

        if issues:
            query_parts.append(
                f"Legal issues: {issues}"
            )

        if facts:
            query_parts.append(
                f"Material facts: {facts}"
            )

        if arguments_query:
            query_parts.append(arguments_query)

        if evidence:
            query_parts.append(
                f"Evidence: {evidence}"
            )

        if statutes:
            query_parts.append(
                f"Relevant provisions: {statutes}"
            )

        if question:
            query_parts.append(
                f"Research question: {question}"
            )

        full_query = "\n".join(query_parts)

        return LegalQuery(
            full_query=full_query,
            facts_query=facts,
            issues_query=issues,
            arguments_query=arguments_query,
            evidence_query=evidence,
            statutes_query=statutes,
        )