/* ============================================================
   FINPILOT DASHBOARD
   Real Flask + Finance Engine + Autonomous Agent
   Production-safe frontend
   ============================================================ */

let financialData = null;
let agentResult = null;
let spendingChart = null;


/* ============================================================
   INIT
   ============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    setupFileUpload();
    setupAgentChat();
    setupNavigation();

    /*
     * Load existing database data when dashboard opens.
     */
    loadDashboardData();

    /*
     * Render locally stored goals if the element exists.
     */
    renderGoals();

    console.log("FinPilot dashboard ready.");

});


/* ============================================================
   LOAD DASHBOARD DATA
   ============================================================ */

async function loadDashboardData() {

    try {

        setDataStatus("Loading data...");

        const response = await fetch(
            "/api/dashboard",
            {
                method: "GET"
            }
        );

        const rawData = await safeJson(response);

        if (!response.ok) {

            throw new Error(
                rawData.error ||
                "Could not load dashboard data."
            );

        }

        const data =
            normalizeDashboardResponse(rawData);

        financialData = data;

        /*
         * Render existing database data.
         */
        renderFinancialOverview(data);
        renderSpending(data);
        renderBudgets(data);
        renderTransactions(data);
        renderRecurring(data);
        renderUnusual(data);

        /*
         * Existing data status.
         */
        if (Number(data.transaction_count || 0) > 0) {

            setDataStatus("Data loaded");

            showUploadStatus(
                `${data.transaction_count} transaction(s) loaded from your data.`
            );

        } else {

            setDataStatus("No data loaded");

        }

    } catch (error) {

        console.error(
            "Dashboard load error:",
            error
        );

        setDataStatus("No data loaded");

    }

}


/* ============================================================
   FILE UPLOAD
   ============================================================ */

function setupFileUpload() {

    const fileInput =
        document.getElementById(
            "statementFile"
        );

    if (!fileInput) {

        console.error(
            "statementFile input not found."
        );

        return;
    }

    fileInput.addEventListener(
        "change",
        async function (event) {

            const file =
                event.target.files[0];

            if (!file) {
                return;
            }

            await uploadStatement(file);

            /*
             * Allow the same file to be selected again.
             */
            fileInput.value = "";

        }
    );

}


async function uploadStatement(file) {

    const extension =
        file.name
            .toLowerCase()
            .split(".")
            .pop();

    const allowedExtensions = [
        "csv",
        "xlsx",
        "xls"
    ];

    if (
        !allowedExtensions.includes(
            extension
        )
    ) {

        showUploadStatus(
            "Only CSV and Excel files are supported.",
            true
        );

        return;
    }


    showUploadStatus(
        "Uploading and analyzing your statement..."
    );

    setDataStatus(
        "Processing"
    );


    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );


    try {

        const response =
            await fetch(
                "/upload",
                {
                    method: "POST",
                    body: formData
                }
            );


        const rawData =
            await safeJson(response);


        if (!response.ok) {

            throw new Error(
                rawData.error ||
                "Could not process the statement."
            );

        }


        /*
         * VERY IMPORTANT:
         *
         * Backend returns:
         *
         * {
         *   success: true,
         *   analysis: {
         *      income: ...
         *   }
         * }
         *
         * Normalize it into flat frontend format.
         */

        financialData =
            normalizeDashboardResponse(
                rawData
            );


        /*
         * Render REAL values.
         */

        renderFinancialOverview(
            financialData
        );

        renderSpending(
            financialData
        );

        renderBudgets(
            financialData
        );

        renderTransactions(
            financialData
        );

        renderRecurring(
            financialData
        );

        renderUnusual(
            financialData
        );


        setDataStatus(
            "Data loaded"
        );


        let statusMessage =
            `${file.name} processed successfully.`;

        if (
            Number.isFinite(
                Number(rawData.added)
            ) ||
            Number.isFinite(
                Number(rawData.skipped)
            )
        ) {

            statusMessage +=
                ` Added: ${Number(rawData.added || 0)},` +
                ` skipped: ${Number(rawData.skipped || 0)}.`;

        }

        showUploadStatus(
            statusMessage
        );


        /*
         * Automatically run autonomous agent.
         */

        await runAutonomousAgent();


        /*
         * Refresh dashboard from database after upload.
         */

        await loadDashboardData();


    } catch (error) {

        console.error(
            "Upload error:",
            error
        );

        setDataStatus(
            "Error"
        );

        showUploadStatus(
            error.message ||
            "Could not process the statement.",
            true
        );

    }

}


/* ============================================================
   NORMALIZE BACKEND RESPONSE
   ============================================================ */

function normalizeDashboardResponse(data) {

    const payload =
        data &&
        data.analysis &&
        typeof data.analysis === "object"
            ? data.analysis
            : (data || {});


    const normalized = {
        success:
            Boolean(
                data &&
                data.success
            ),

        filename:
            data &&
            data.filename
                ? data.filename
                : "",

        message:
            data &&
            data.message
                ? data.message
                : "",

        added:
            Number(
                data &&
                data.added
                    ? data.added
                    : 0
            ),

        skipped:
            Number(
                data &&
                data.skipped
                    ? data.skipped
                    : 0
            )
    };


    /*
     * Financial totals
     */

    normalized.income =
        Number(
            payload.income || 0
        );

    normalized.expenses =
        Number(
            payload.expenses || 0
        );

    normalized.savings =
        Number(
            payload.savings || 0
        );

    normalized.savings_rate =
        Number(
            payload.savings_rate || 0
        );


    /*
     * Transaction count
     */

    normalized.transaction_count =
        Number(
            payload.transaction_count ||
            (
                Array.isArray(
                    payload.transactions
                )
                    ? payload.transactions.length
                    : 0
            )
        );


    /*
     * Categories
     */

    normalized.category_spending =
        payload.category_spending &&
        typeof payload.category_spending === "object"
            ? payload.category_spending
            : {};


    /*
     * Recurring
     */

    normalized.recurring =
        Array.isArray(
            payload.recurring
        )
            ? payload.recurring
            : [];


    /*
     * Unusual
     */

    normalized.unusual =
        Array.isArray(
            payload.unusual
        )
            ? payload.unusual
            : [];


    normalized.unusual_spending =
        Array.isArray(
            payload.unusual_spending
        )
            ? payload.unusual_spending
            : normalized.unusual;


    /*
     * Monthly spending
     */

    normalized.monthly_spending =
        payload.monthly_spending &&
        typeof payload.monthly_spending === "object"
            ? payload.monthly_spending
            : {};


    /*
     * Transactions
     */

    normalized.transactions =
        Array.isArray(
            payload.transactions
        )
            ? payload.transactions.map(
                normalizeTransaction
            )
            : [];


    /*
     * Recent transactions
     */

    if (
        Array.isArray(
            payload.recent_transactions
        )
    ) {

        normalized.recent_transactions =
            payload.recent_transactions.map(
                normalizeTransaction
            );

    } else {

        normalized.recent_transactions =
            normalized.transactions
                .slice(
                    -10
                )
                .reverse();

    }


    /*
     * Budget progress
     */

    normalized.budget_progress =
        Array.isArray(
            payload.budget_progress
        )
            ? payload.budget_progress
            : [];


    /*
     * Optional fields used by other backend versions.
     */

    normalized.budgets =
        Array.isArray(
            payload.budgets
        )
            ? payload.budgets
            : [];

    normalized.goals =
        Array.isArray(
            payload.goals
        )
            ? payload.goals
            : [];

    normalized.goal_impact =
        payload.goal_impact || {};

    normalized.insights =
        Array.isArray(
            payload.insights
        )
            ? payload.insights
            : [];


    return normalized;

}


/* ============================================================
   NORMALIZE ONE TRANSACTION
   ============================================================ */

function normalizeTransaction(tx) {

    tx =
        tx && typeof tx === "object"
            ? tx
            : {};


    return {

        date:
            tx.date ||
            tx.Date ||
            "",

        description:
            tx.description ||
            tx.Description ||
            "Unknown transaction",

        amount:
            Number(
                tx.amount ??
                tx.Amount ??
                0
            ),

        category:
            tx.category ||
            tx.Category ||
            "Other",

        type:
            tx.type ||
            tx.Type ||
            ""

    };

}


/* ============================================================
   AUTONOMOUS AGENT
   ============================================================ */

async function runAutonomousAgent() {

    if (!financialData) {

        console.error(
            "No financial data available."
        );

        return;
    }


    const empty =
        document.getElementById(
            "agentEmpty"
        );

    const activity =
        document.getElementById(
            "agentActivity"
        );

    const report =
        document.getElementById(
            "agentReport"
        );

    const chat =
        document.getElementById(
            "agentChat"
        );


    if (empty) {
        empty.classList.add(
            "hidden"
        );
    }

    if (activity) {
        activity.classList.remove(
            "hidden"
        );
    }

    if (report) {
        report.classList.add(
            "hidden"
        );
    }

    if (chat) {
        chat.classList.add(
            "hidden"
        );
    }


    setAgentStatus(
        "Investigating..."
    );

    setSidebarAgentStatus(
        "Investigating your finances"
    );


    renderAgentActivity([

        {
            title:
                "Understanding your financial data",

            description:
                "Building the financial profile...",

            active:
                true
        },

        {
            title:
                "Selecting analysis tools",

            description:
                "Determining what needs investigation...",

            active:
                false
        },

        {
            title:
                "Investigating patterns",

            description:
                "Checking spending and cash flow...",

            active:
                false
        }

    ]);


    try {

        const response =
            await fetch(
                "/agent/analyze",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            financial_data:
                                financialData
                        })
                }
            );


        const data =
            await safeJson(
                response
            );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Agent analysis failed."
            );

        }


        agentResult =
            data;


        renderAgentReport(
            data
        );


        if (activity) {
            activity.classList.add(
                "hidden"
            );
        }

        if (report) {
            report.classList.remove(
                "hidden"
            );
        }

        if (chat) {
            chat.classList.remove(
                "hidden"
            );
        }


        setAgentStatus(
            "Analysis complete"
        );

        setSidebarAgentStatus(
            "Analysis complete"
        );


    } catch (error) {

        console.error(
            "Agent error:",
            error
        );


        setAgentStatus(
            "Analysis failed"
        );

        setSidebarAgentStatus(
            "Analysis failed"
        );


        renderAgentError(
            error.message
        );

    }

}


/* ============================================================
   AGENT REPORT
   ============================================================ */

function renderAgentReport(result) {

    const report =
        result &&
        result.report
            ? result.report
            : (
                result || {}
            );


    setText(
        "agentHeadline",
        report.headline ||
        "Your financial analysis is ready."
    );


    setText(
        "agentOverview",
        report.summary ||
        report.overview ||
        "FinPilot completed its investigation."
    );


    setText(
        "agentSpending",
        firstItem(
            report.spending_risks ||
            report.spending_pattern
        ) ||
        "No major spending pattern identified."
    );


    setText(
        "agentRecurring",
        firstItem(
            report.recurring_payments
        ) ||
        summarizeRecurring()
    );


    setText(
        "agentAttention",
        firstItem(
            report.spending_risks ||
            report.attention_needed
        ) ||
        "No major attention item identified."
    );


    setText(
        "agentBudget",
        firstItem(
            report.recommendations ||
            report.budget_check
        ) ||
        summarizeBudgets()
    );


    setText(
        "agentInsight",
        report.agent_insight ||
        "FinPilot completed its analysis using the available financial data."
    );


    renderList(
        "agentKeyInsights",
        report.key_insights ||
        []
    );


    renderList(
        "agentRisks",
        report.spending_risks ||
        report.attention_needed ||
        []
    );


    renderList(
        "agentOpportunities",
        report.savings_opportunities ||
        []
    );


    renderRecommendations(
        report.recommendations ||
        []
    );


    renderToolTrace(
        result.tools_used ||
        []
    );

}


/* ============================================================
   AGENT ACTIVITY
   ============================================================ */

function renderAgentActivity(steps) {

    const container =
        document.getElementById(
            "activityList"
        );

    if (!container) {
        return;
    }


    container.innerHTML =
        (
            Array.isArray(steps)
                ? steps
                : []
        )
        .map(
            function (step) {

                return `

                    <div class="activity-step ${
                        step.active
                            ? "active"
                            : ""
                    }">

                        <div class="activity-icon">

                            ${
                                step.active
                                    ? "◌"
                                    : "✓"
                            }

                        </div>

                        <div>

                            <strong>
                                ${
                                    escapeHTML(
                                        step.title
                                    )
                                }
                            </strong>

                            <span>
                                ${
                                    escapeHTML(
                                        step.description
                                    )
                                }
                            </span>

                        </div>

                    </div>

                `;

            }
        )
        .join("");

}


/* ============================================================
   AGENT ERROR
   ============================================================ */

function renderAgentError(message) {

    const activity =
        document.getElementById(
            "agentActivity"
        );

    if (!activity) {
        return;
    }


    activity.classList.remove(
        "hidden"
    );


    const list =
        document.getElementById(
            "activityList"
        );

    if (!list) {
        return;
    }


    list.innerHTML = `

        <div class="activity-step active">

            <div class="activity-icon">
                !
            </div>

            <div>

                <strong>
                    Agent analysis failed
                </strong>

                <span>
                    ${
                        escapeHTML(
                            message
                        )
                    }
                </span>

            </div>

        </div>

    `;

}


/* ============================================================
   TOOL TRACE
   ============================================================ */

function renderToolTrace(tools) {

    const container =
        document.getElementById(
            "agentToolTrace"
        );

    if (!container) {
        return;
    }


    if (
        !Array.isArray(tools) ||
        !tools.length
    ) {

        container.innerHTML =
            "<span>No tool trace available.</span>";

        return;
    }


    container.innerHTML =
        tools
            .map(
                function (tool) {

                    return `

                        <span class="tool-item">
                            ✓ ${
                                escapeHTML(
                                    formatToolName(
                                        tool
                                    )
                                )
                            }
                        </span>

                    `;

                }
            )
            .join("");

}


/* ============================================================
   LIST RENDERER
   ============================================================ */

function renderList(
    id,
    items
) {

    const container =
        document.getElementById(
            id
        );

    if (!container) {
        return;
    }


    if (
        !Array.isArray(items) ||
        !items.length
    ) {

        container.innerHTML = `

            <div class="empty-inline">
                No specific items identified.
            </div>

        `;

        return;
    }


    container.innerHTML =
        items
            .map(
                function (item) {

                    const text =
                        typeof item === "string"
                            ? item
                            : (
                                item.text ||
                                item.description ||
                                item.title ||
                                ""
                            );


                    return `

                        <div class="insight-list-item">

                            <span>
                                •
                            </span>

                            <p>
                                ${
                                    escapeHTML(
                                        text
                                    )
                                }
                            </p>

                        </div>

                    `;

                }
            )
            .join("");

}


/* ============================================================
   RECOMMENDATIONS
   ============================================================ */

function renderRecommendations(
    items
) {

    const container =
        document.getElementById(
            "agentRecommendations"
        );

    if (!container) {
        return;
    }


    if (
        !Array.isArray(items) ||
        !items.length
    ) {

        container.innerHTML = `

            <div class="empty-inline">
                No recommendations generated.
            </div>

        `;

        return;
    }


    container.innerHTML =
        items
            .map(
                function (
                    item,
                    index
                ) {

                    const text =
                        typeof item === "string"
                            ? item
                            : (
                                item.text ||
                                item.description ||
                                item.title ||
                                ""
                            );


                    return `

                        <div class="recommendation-item">

                            <div class="recommendation-number">
                                ${
                                    index + 1
                                }
                            </div>

                            <p>
                                ${
                                    escapeHTML(
                                        text
                                    )
                                }
                            </p>

                        </div>

                    `;

                }
            )
            .join("");

}


/* ============================================================
   FINANCIAL OVERVIEW
   ============================================================ */

function renderFinancialOverview(
    data
) {

    setText(
        "income",
        formatINR(
            data.income
        )
    );


    setText(
        "expenses",
        formatINR(
            data.expenses
        )
    );


    setText(
        "savings",
        formatINR(
            data.savings
        )
    );


    setText(
        "savingsRate",
        `${Number(
            data.savings_rate || 0
        ).toFixed(2)}%`
    );


    /*
     * Optional transaction count support.
     */

    setText(
        "transactionCount",
        String(
            Number(
                data.transaction_count ||
                0
            )
        )
    );

}


/* ============================================================
   SPENDING CHART
   ============================================================ */

function renderSpending(
    data
) {

    const canvas =
        document.getElementById(
            "spendingChart"
        );

    const empty =
        document.getElementById(
            "chartEmpty"
        );

    if (!canvas) {
        return;
    }


    const categories =
        data.category_spending || {};


    const entries =
        Object.entries(
            categories
        )
        .filter(
            function (item) {

                return Number(
                    item[1]
                ) > 0;

            }
        )
        .sort(
            function (a, b) {

                return (
                    Number(b[1]) -
                    Number(a[1])
                );

            }
        );


    if (!entries.length) {

        if (empty) {
            empty.style.display =
                "flex";
        }

        if (spendingChart) {

            spendingChart.destroy();

            spendingChart =
                null;

        }

        return;
    }


    if (empty) {
        empty.style.display =
            "none";
    }


    if (
        typeof Chart ===
        "undefined"
    ) {

        console.error(
            "Chart.js was not loaded."
        );

        return;
    }


    if (spendingChart) {

        spendingChart.destroy();

        spendingChart =
            null;
    }


    const chartColors = [

        "#4F46E5",
        "#7C3AED",
        "#F97316",
        "#EC4899",
        "#10B981",
        "#F59E0B",
        "#06B6D4",
        "#EF4444",
        "#8B5CF6",
        "#14B8A6"

    ];


    spendingChart =
        new Chart(
            canvas.getContext(
                "2d"
            ),
            {

                type:
                    "doughnut",

                data: {

                    labels:
                        entries.map(
                            function (
                                item
                            ) {

                                return item[0];

                            }
                        ),

                    datasets: [

                        {

                            data:
                                entries.map(
                                    function (
                                        item
                                    ) {

                                        return Number(
                                            item[1]
                                        );

                                    }
                                ),

                            backgroundColor:
                                entries.map(
                                    function (
                                        _,
                                        index
                                    ) {

                                        return (
                                            chartColors[
                                                index %
                                                chartColors.length
                                            ]
                                        );

                                    }
                                ),

                            borderWidth:
                                2,

                            borderColor:
                                "#ffffff"

                        }

                    ]

                },

                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    cutout:
                        "68%",

                    plugins: {

                        legend: {

                            position:
                                "bottom"

                        },

                        tooltip: {

                            callbacks: {

                                label:
                                    function (
                                        context
                                    ) {

                                        const value =
                                            Number(
                                                context.raw ||
                                                0
                                            );

                                        return (
                                            " " +
                                            context.label +
                                            ": " +
                                            formatINR(
                                                value
                                            )
                                        );

                                    }

                            }

                        }

                    }

                }

            }
        );

}


/* ============================================================
   BUDGETS
   ============================================================ */

function renderBudgets(
    data
) {

    const rows =
        document.querySelectorAll(
            ".budget-row"
        );


    const budgets =
        Array.isArray(
            data.budget_progress
        )
            ? data.budget_progress
            : [];


    rows.forEach(
        function (row) {

            const category =
                row.dataset.category;


            const budget =
                budgets.find(
                    function (item) {

                        return (
                            String(
                                item.category
                            )
                            .toLowerCase() ===

                            String(
                                category
                            )
                            .toLowerCase()
                        );

                    }
                );


            if (!budget) {
                return;
            }


            const amount =
                row.querySelector(
                    ".budget-amount"
                );


            const progress =
                row.querySelector(
                    ".progress-value"
                );


            if (amount) {

                amount.textContent =
                    `${formatINR(
                        budget.spent || 0
                    )} / ${formatINR(
                        budget.budget || 0
                    )}`;

            }


            if (progress) {

                progress.style.width =
                    `${Math.min(
                        Number(
                            budget.percentage ||
                            0
                        ),
                        100
                    )}%`;

            }

        }
    );

}


/* ============================================================
   TRANSACTIONS
   ============================================================ */

function renderTransactions(
    data
) {

    const container =
        document.getElementById(
            "recentTransactions"
        );

    if (!container) {
        return;
    }


    const transactions =
        Array.isArray(
            data.recent_transactions
        )
            ? data.recent_transactions
            : [];


    if (!transactions.length) {

        container.innerHTML = `

            <div class="transaction-empty">

                <div class="empty-icon">
                    ▤
                </div>

                <strong>
                    No transactions found
                </strong>

                <span>
                    Your statement contains no usable transactions.
                </span>

            </div>

        `;

        return;
    }


    container.innerHTML =
        transactions.map(
            function (tx) {

                const normalized =
                    normalizeTransaction(
                        tx
                    );


                const amount =
                    Number(
                        normalized.amount
                    );


                return `

                    <div class="transaction-row">

                        <div class="transaction-date">
                            ${
                                escapeHTML(
                                    normalized.date
                                )
                            }
                        </div>

                        <div class="transaction-description">
                            ${
                                escapeHTML(
                                    normalized.description
                                )
                            }
                        </div>

                        <div class="transaction-category">
                            ${
                                escapeHTML(
                                    normalized.category
                                )
                            }
                        </div>

                        <div class="transaction-amount ${
                            amount > 0
                                ? "income"
                                : "expense"
                        }">

                            ${
                                amount > 0
                                    ? "+"
                                    : "-"
                            }

                            ${
                                formatINR(
                                    Math.abs(
                                        amount
                                    )
                                )
                            }

                        </div>

                    </div>

                `;

            }
        )
        .join("");

}


/* ============================================================
   RECURRING
   ============================================================ */

function renderRecurring(
    data
) {

    const container =
        document.getElementById(
            "recurringPayments"
        );

    if (!container) {
        return;
    }


    const recurring =
        Array.isArray(
            data.recurring
        )
            ? data.recurring
            : [];


    if (!recurring.length) {

        container.innerHTML = `

            <div class="recurring-empty">

                <div class="empty-icon">
                    ↻
                </div>

                <strong>
                    No recurring patterns detected
                </strong>

                <span>
                    No repeated payments were found.
                </span>

            </div>

        `;

        return;
    }


    container.innerHTML =
        recurring.map(
            function (item) {

                return `

                    <div class="recurring-row">

                        <div>

                            <strong>
                                ${
                                    escapeHTML(
                                        item.description ||
                                        "Recurring payment"
                                    )
                                }
                            </strong>

                            <span>
                                ${
                                    Number(
                                        item.payments ||
                                        0
                                    )
                                }
                                payments detected
                            </span>

                        </div>

                        <strong>
                            ${
                                formatINR(
                                    item.amount ||
                                    0
                                )
                            }
                        </strong>

                    </div>

                `;

            }
        )
        .join("");

}


/* ============================================================
   UNUSUAL SPENDING
   ============================================================ */

function renderUnusual(
    data
) {

    const container =
        document.getElementById(
            "unusualSpending"
        );

    if (!container) {
        return;
    }


    const unusual =
        Array.isArray(
            data.unusual_spending
        )
            ? data.unusual_spending
            : [];


    if (!unusual.length) {

        container.innerHTML = `

            <div class="unusual-empty">

                <div class="empty-icon">
                    ✓
                </div>

                <strong>
                    No unusual spending detected
                </strong>

                <span>
                    No expense stood out against the observed pattern.
                </span>

            </div>

        `;

        return;
    }


    container.innerHTML =
        unusual.map(
            function (item) {

                return `

                    <div class="unusual-row">

                        <div>

                            <strong>
                                ${
                                    escapeHTML(
                                        item.description ||
                                        "Unusual transaction"
                                    )
                                }
                            </strong>

                            <span>

                                ${
                                    escapeHTML(
                                        item.date ||
                                        ""
                                    )
                                }

                                · Average:

                                ${
                                    formatINR(
                                        item.average ||
                                        0
                                    )
                                }

                            </span>

                        </div>

                        <strong>
                            ${
                                formatINR(
                                    item.amount ||
                                    0
                                )
                            }
                        </strong>

                    </div>

                `;

            }
        )
        .join("");

}


/* ============================================================
   CHAT SETUP
   ============================================================ */

function setupAgentChat() {

    const button =
        document.getElementById(
            "agentAsk"
        );


    const input =
        document.getElementById(
            "agentQuestion"
        );


    if (!button || !input) {
        return;
    }


    button.addEventListener(
        "click",
        askAgent
    );


    input.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key ===
                "Enter"
            ) {

                event.preventDefault();

                askAgent();

            }

        }
    );

}


/* ============================================================
   CHAT WITH AGENT
   ============================================================ */

async function askAgent() {

    const input =
        document.getElementById(
            "agentQuestion"
        );


    const answer =
        document.getElementById(
            "chatAnswer"
        );


    if (!input || !answer) {
        return;
    }


    const question =
        input.value.trim();


    if (!question) {
        return;
    }


    if (!financialData) {

        answer.classList.remove(
            "hidden"
        );

        answer.textContent =
            "Upload a statement before asking FinPilot.";

        return;
    }


    answer.classList.remove(
        "hidden"
    );


    answer.textContent =
        "FinPilot is analyzing your question...";


    try {

        const response =
            await fetch(
                "/agent/chat",
                {
                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify({

                            message:
                                question,

                            financial_data:
                                financialData

                        })

                }
            );


        const data =
            await safeJson(
                response
            );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Could not answer the question."
            );

        }


        const responseText =
            data.answer ||
            data.response ||
            data.message ||
            data.agent_insight ||
            "No answer returned.";


        answer.textContent =
            responseText;


        input.value =
            "";

    } catch (error) {

        console.error(
            "Agent chat error:",
            error
        );

        answer.textContent =
            error.message;

    }

}


/* ============================================================
   GOALS
   ============================================================ */

function addGoal() {

    const title =
        prompt(
            "What are you saving for?"
        );


    if (!title) {
        return;
    }


    const targetInput =
        prompt(
            "What is your target amount in ₹?"
        );


    const target =
        Number(
            targetInput
        );


    if (
        !Number.isFinite(
            target
        ) ||
        target <= 0
    ) {

        alert(
            "Please enter a valid target amount."
        );

        return;
    }


    let goals = [];

    try {

        goals =
            JSON.parse(
                localStorage.getItem(
                    "finpilot_goals"
                ) ||
                "[]"
            );

    } catch (error) {

        goals =
            [];

    }


    goals.push({

        id:
            Date.now(),

        title:
            title,

        target:
            target,

        current:
            0

    });


    localStorage.setItem(
        "finpilot_goals",
        JSON.stringify(
            goals
        )
    );


    renderGoals();

}


function renderGoals() {

    const container =
        document.getElementById(
            "financialGoals"
        );


    if (!container) {
        return;
    }


    let goals = [];

    try {

        goals =
            JSON.parse(
                localStorage.getItem(
                    "finpilot_goals"
                ) ||
                "[]"
            );

    } catch (error) {

        goals =
            [];

    }


    if (!goals.length) {
        return;
    }


    container.innerHTML =
        goals.map(
            function (goal) {

                const target =
                    Number(
                        goal.target ||
                        0
                    );

                const current =
                    Number(
                        goal.current ||
                        0
                    );


                const percentage =
                    target > 0
                        ? Math.min(
                            (
                                current /
                                target
                            ) * 100,
                            100
                        )
                        : 0;


                return `

                    <div class="goal-card">

                        <strong>
                            ${
                                escapeHTML(
                                    goal.title
                                )
                            }
                        </strong>

                        <span>
                            ${
                                formatINR(
                                    current
                                )
                            }
                            /
                            ${
                                formatINR(
                                    target
                                )
                            }
                        </span>

                        <div class="progress-bar">

                            <div
                                class="progress-value"
                                style="width:${percentage}%"
                            ></div>

                        </div>

                    </div>

                `;

            }
        )
        .join("");

}


/* ============================================================
   NAVIGATION
   ============================================================ */

function setupNavigation() {

    const navItems =
        document.querySelectorAll(
            ".nav-item"
        );


    navItems.forEach(
        function (item) {

            item.addEventListener(
                "click",
                function () {

                    navItems.forEach(
                        function (nav) {

                            nav.classList.remove(
                                "active"
                            );

                        }
                    );


                    item.classList.add(
                        "active"
                    );

                }
            );

        }
    );

}


/* ============================================================
   STATUS
   ============================================================ */

function setDataStatus(
    text
) {

    const element =
        document.getElementById(
            "dataStatus"
        );


    if (element) {

        element.textContent =
            text;

    }

}


function setAgentStatus(
    text
) {

    const element =
        document.getElementById(
            "agentStatus"
        );


    if (element) {

        element.textContent =
            text;

    }

}


function setSidebarAgentStatus(
    text
) {

    const element =
        document.getElementById(
            "sidebarAgentStatus"
        );


    if (element) {

        element.textContent =
            text;

    }

}


function showUploadStatus(
    message,
    isError = false
) {

    const element =
        document.getElementById(
            "uploadStatus"
        );


    if (!element) {
        return;
    }


    element.textContent =
        message;


    element.classList.toggle(
        "error",
        Boolean(
            isError
        )
    );

}


/* ============================================================
   HELPERS
   ============================================================ */

function setText(
    id,
    value
) {

    const element =
        document.getElementById(
            id
        );


    if (element) {

        element.textContent =
            value ??
            "";

    }

}


function formatINR(
    value
) {

    const number =
        Number(
            value ||
            0
        );


    return (
        "₹" +
        number.toLocaleString(
            "en-IN",
            {
                maximumFractionDigits:
                    2
            }
        )
    );

}


function escapeHTML(
    value
) {

    return String(
        value ??
        ""
    )
    .replace(
        /&/g,
        "&amp;"
    )
    .replace(
        /</g,
        "&lt;"
    )
    .replace(
        />/g,
        "&gt;"
    )
    .replace(
        /"/g,
        "&quot;"
    )
    .replace(
        /'/g,
        "&#039;"
    );

}


function formatToolName(
    tool
) {

    return String(
        tool ||
        ""
    )
    .replace(
        /_/g,
        " "
    )
    .replace(
        /\b\w/g,
        function (
            char
        ) {

            return char.toUpperCase();

        }
    );

}


function firstItem(
    items
) {

    if (
        !Array.isArray(
            items
        ) ||
        !items.length
    ) {

        return "";

    }


    const item =
        items[0];


    if (
        typeof item ===
        "string"
    ) {

        return item;

    }


    return (
        item.text ||
        item.description ||
        item.title ||
        ""
    );

}


function summarizeRecurring() {

    if (
        !financialData ||
        !Array.isArray(
            financialData.recurring
        ) ||
        !financialData.recurring.length
    ) {

        return (
            "No recurring payments detected."
        );

    }


    return (

        financialData.recurring.length +
        " recurring payment patterns detected."

    );

}


function summarizeBudgets() {

    if (
        !financialData ||
        !Array.isArray(
            financialData.budget_progress
        )
    ) {

        return (
            "Budget analysis unavailable."
        );

    }


    const over =
        financialData.budget_progress.filter(
            function (
                item
            ) {

                return (
                    Number(
                        item.percentage ||
                        0
                    ) > 100
                );

            }
        );


    if (
        over.length
    ) {

        return (

            over.length +
            " budget categor" +
            (
                over.length > 1
                    ? "ies"
                    : "y"
            ) +
            " exceeded the configured limit."

        );

    }


    return (
        "No configured budget category exceeded its limit."
    );

}


/* ============================================================
   SAFE JSON PARSER
   ============================================================ */

async function safeJson(
    response
) {

    const text =
        await response.text();


    if (!text) {
        return {};
    }


    try {

        return JSON.parse(
            text
        );

    } catch (error) {

        return {
            error:
                text
        };

    }

}


/* ============================================================
   OPTIONAL GLOBAL ACCESS
   ============================================================ */

window.FinPilot = {

    uploadStatement:
        uploadStatement,

    loadDashboardData:
        loadDashboardData,

    askAgent:
        askAgent,

    addGoal:
        addGoal,

    renderGoals:
        renderGoals

};