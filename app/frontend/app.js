const analyzeButton =
    document.getElementById("analyzeButton");

const queryInput =
    document.getElementById("query");

const yearInput =
    document.getElementById("year");

const topKInput =
    document.getElementById("topK");

const loading =
    document.getElementById("loading");

const results =
    document.getElementById("results");

const answer =
    document.getElementById("answer");

const citations =
    document.getElementById("citations");


analyzeButton.addEventListener(
    "click",
    async () => {

        const query = queryInput.value.trim();

        if (!query) {
            alert("Please enter a legal research question.");
            return;
        }

        loading.classList.remove("hidden");
        results.classList.add("hidden");

        analyzeButton.disabled = true;

        try {

            const response = await fetch(
                "/api/query",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({
                        query: query,
                        as_of_year:
                            Number(yearInput.value) || null,
                        top_k:
                            Number(topKInput.value),
                        use_graph: false
                    })
                }
            );

            if (!response.ok) {
                throw new Error(
                    "The server could not process the query."
                );
            }

            const data = await response.json();

            answer.innerText = data.answer;

            citations.innerHTML = "";

            data.citations.forEach(
                (citation) => {

                    const item =
                        document.createElement("div");

                    item.className = "citation";

                    item.innerHTML = `
                        <div class="citation-title">
                            [${citation.citation_id}]
                            ${escapeHtml(citation.case_name)}
                        </div>

                        <div class="citation-meta">
                            Document:
                            ${escapeHtml(citation.doc_id)}
                            ${citation.page
                                ? ` · Page ${citation.page}`
                                : ""}
                        </div>

                        <div class="citation-text">
                            ${escapeHtml(
                                citation.supporting_text
                            )}
                        </div>
                    `;

                    citations.appendChild(item);
                }
            );

            results.classList.remove("hidden");

        } catch (error) {

            alert(error.message);

        } finally {

            loading.classList.add("hidden");
            analyzeButton.disabled = false;
        }
    }
);


function escapeHtml(text) {

    const div = document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}