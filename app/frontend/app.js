const analyzeButton =
    document.getElementById("analyzeButton");

const loading =
    document.getElementById("loading");

const results =
    document.getElementById("results");

const analysis =
    document.getElementById("analysis");

const precedents =
    document.getElementById("precedents");

const retrievalMode =
    document.getElementById("retrievalMode");


analyzeButton.addEventListener(
    "click",
    async () => {

        const request = {

            facts:
                document
                    .getElementById("facts")
                    .value
                    .trim(),

            legal_issues:
                document
                    .getElementById("issues")
                    .value
                    .trim(),

            petitioner_arguments:
                document
                    .getElementById("petitioner")
                    .value
                    .trim(),

            respondent_arguments:
                document
                    .getElementById("respondent")
                    .value
                    .trim(),

            evidence:
                document
                    .getElementById("evidence")
                    .value
                    .trim(),

            statutes:
                document
                    .getElementById("statutes")
                    .value
                    .trim(),

            question:
                document
                    .getElementById("question")
                    .value
                    .trim(),

            top_k:
                Number(
                    document
                        .getElementById("topK")
                        .value
                ),

            use_graph: false
        };


        if (
            !request.facts
            && !request.legal_issues
            && !request.question
        ) {

            alert(
                "Please provide at least facts, "
                + "a legal issue, or a research question."
            );

            return;
        }


        loading.classList.remove("hidden");
        results.classList.add("hidden");

        analyzeButton.disabled = true;


        try {

            const response = await fetch(
                "/api/analyze",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(request)
                }
            );


            if (!response.ok) {

                throw new Error(
                    "The case could not be analyzed."
                );
            }


            const data =
                await response.json();


            analysis.innerText =
                data.analysis;


            retrievalMode.innerText =
                data.retrieval_mode;


            precedents.innerHTML = "";


            if (
                data.precedents.length === 0
            ) {

                precedents.innerHTML =
                    "<p>No relevant precedent found.</p>";

            }


            data.precedents.forEach(
                (precedent, index) => {

                    const card =
                        document.createElement(
                            "div"
                        );

                    card.className =
                        "precedent-card";


                    const reasons =
                        precedent.reasons
                            .map(
                                reason =>
                                    `<li>${escapeHtml(reason)}</li>`
                            )
                            .join("");


                    const passages =
                        precedent.passages
                            .map(
                                passage => `
                                    <div class="passage">

                                        <div class="passage-meta">

                                            ${escapeHtml(
                                                passage.section
                                                || "Passage"
                                            )}

                                            ${passage.page
                                                ? ` · Page ${passage.page}`
                                                : ""
                                            }

                                        </div>

                                        <div>
                                            ${escapeHtml(
                                                passage.text
                                            )}
                                        </div>

                                    </div>
                                `
                            )
                            .join("");


                    card.innerHTML = `

                        <div class="precedent-number">
                            ${index + 1}
                        </div>

                        <h4>
                            ${escapeHtml(
                                precedent.case_name
                            )}
                        </h4>

                        ${
                            precedent.score !== null
                            && precedent.score !== undefined
                                ? `
                                    <div class="score">
                                        Relevance score:
                                        ${precedent.score}
                                    </div>
                                `
                                : ""
                        }

                        ${
                            reasons
                                ? `
                                    <div class="why">
                                        <strong>
                                            Why relevant
                                        </strong>

                                        <ul>
                                            ${reasons}
                                        </ul>
                                    </div>
                                `
                                : ""
                        }

                        ${passages}
                    `;


                    precedents.appendChild(
                        card
                    );
                }
            );


            results.classList.remove(
                "hidden"
            );


        } catch (error) {

            alert(error.message);

        } finally {

            loading.classList.add(
                "hidden"
            );

            analyzeButton.disabled =
                false;
        }
    }
);


function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent =
        text || "";

    return div.innerHTML;
}