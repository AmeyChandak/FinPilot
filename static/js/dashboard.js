/* ============================================================
   FINPILOT DASHBOARD
   Final version for current dashboard.html
   ============================================================ */

let financialData = null;
let selectedFileObject = null;
let spendingChart = null;


/* ============================================================
   INITIALIZE
   ============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    setupFilePicker();
    setupQuickQuestions();
    setupAssistant();

    loadDashboardData();
    loadGoalImpact();
    loadBudgetAnalysis();

    console.log("FinPilot dashboard ready.");

});


/* ============================================================
   FILE PICKER
   ============================================================ */

function setupFilePicker() {

    const fileInput =
        document.getElementById("fileInput");

    const selectedFile =
        document.getElementById("selectedFile");

    const uploadBtn =
        document.getElementById("uploadBtn");


    if (!fileInput) {

        console.error(
            "fileInput element not found."
        );

        return;
    }


    fileInput.addEventListener(
        "change",
        function () {

            const file =
                fileInput.files &&
                fileInput.files[0];


            if (!file) {

                selectedFileObject =
                    null;

                if (selectedFile) {

                    selectedFile.style.display =
                        "none";

                    selectedFile.textContent =
                        "";

                }

                return;
            }


            selectedFileObject =
                file;


            if (selectedFile) {

                selectedFile.style.display =
                    "block";

                selectedFile.innerHTML = `

                    <strong>Selected file:</strong>

                    <span>
                        ${escapeHTML(file.name)}
                    </span>

                `;

            }


            if (uploadBtn) {

                uploadBtn.disabled =
                    false;

                uploadBtn.textContent =
                    "Analyze Statement";

            }


            showUploadStatus(
                `File selected: ${file.name}`
            );

        }
    );

}


/* ============================================================
   UPLOAD STATEMENT
   Called from:
   onclick="uploadStatement()"
   ============================================================ */

async function uploadStatement() {

    const fileInput =
        document.getElementById("fileInput");

    const uploadBtn =
        document.getElementById("uploadBtn");


    const file =
        selectedFileObject ||
        (
            fileInput &&
            fileInput.files &&
            fileInput.files[0]
        );


    if (!file) {

        alert(
            "Please choose a file first."
        );

        return;
    }


    const extension =
        file.name
            .split(".")
            .pop()
            .toLowerCase();


    const allowedExtensions = [

        "csv",
        "xlsx",
        "xls",
        "pdf",
        "docx",
        "jpg",
        "jpeg",
        "png"

    ];


    if (
        !allowedExtensions.includes(
            extension
        )
    ) {

        showUploadStatus(
            "Unsupported file format.",
            true
        );

        return;
    }


    /*
     * Disable button while processing.
     */

    if (uploadBtn) {

        uploadBtn.disabled =
            true;

        uploadBtn.textContent =
            "Analyzing...";

    }


    setDataStatus(
        "Processing"
    );


    showUploadStatus(
        "Uploading and analyzing your financial statement..."
    );


    /*
     * FormData
     */

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

                    method:
                        "POST",

                    body:
                        formData

                }
            );


        const data =
            await safeJson(
                response
            );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Could not analyze the statement."
            );

        }


        /*
         * IMPORTANT:
         *
         * Upload API returns:
         *
         * {
         *   success: true,
         *   analysis: {
         *      income,
         *      expenses,
         *      savings,
         *      ...
         *   }
         * }
         */

        financialData =
            normalizeUploadResponse(
                data
            );


        /*
         * Render the uploaded statement DIRECTLY.
         *
         * Do NOT call loadDashboardData()
         * here because that can overwrite this
         * response with empty database values.
         */

        renderFinancialOverview(
            financialData
        );

        renderSpending(
            financialData
        );

        renderCategories(
            financialData
        );

        renderRecurring(
            financialData
        );

        renderUnusual(
            financialData
        );

        renderMonthlySpending(
            financialData
        );

        renderTransactions(
            financialData
        );


        /*
         * Success message
         */

        let message =
            data.message ||
            `Successfully analyzed ${financialData.transaction_count} transaction(s).`;


        const added =
            Number(
                data.added ||
                0
            );


        const skipped =
            Number(
                data.skipped ||
                0
            );


        if (
            added ||
            skipped
        ) {

            message +=
                ` Added: ${added}.` +
                ` Skipped duplicates: ${skipped}.`;

        }


        showUploadStatus(
            message
        );


        showAIResult(
            message
        );


        setDataStatus(
            "Data loaded"
        );


        /*
         * Refresh separate DB sections.
         * These will not overwrite financialData.
         */

        await loadGoalImpact();

        await loadBudgetAnalysis();


        /*
         * Run autonomous analysis.
         */

        await runAutonomousAgent();


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


        showAIResult(
            error.message ||
            "Could not process the statement.",
            true
        );

    } finally {

        if (uploadBtn) {

            uploadBtn.disabled =
                false;

            uploadBtn.textContent =
                "Analyze Statement";

        }


        /*
         * Reset input so the same file
         * can be selected again.
         */

        if (fileInput) {

            fileInput.value =
                "";

        }

    }

}


/* ============================================================
   NORMALIZE UPLOAD RESPONSE
   ============================================================ */

function normalizeUploadResponse(
    data
) {

    const source =
        data &&
        data.analysis &&
        typeof data.analysis === "object"
            ? data.analysis
            : (
                data ||
                {}
            );


    const transactions =
        Array.isArray(
            source.transactions
        )
            ? source.transactions.map(
                normalizeTransaction
            )
            : [];


    return {

        success:
            data &&
            data.success !== false,

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
                data.added ||
                0
            ),

        skipped:
            Number(
                data &&
                data.skipped ||
                0
            ),

        income:
            Number(
                source.income ||
                0
            ),

        expenses:
            Number(
                source.expenses ||
                0
            ),

        savings:
            Number(
                source.savings ||
                0
            ),

        savings_rate:
            Number(
                source.savings_rate ||
                0
            ),

        transaction_count:
            Number(
                source.transaction_count ||
                transactions.length ||
                0
            ),

        category_spending:
            source.category_spending ||
            {},

        recurring:
            Array.isArray(
                source.recurring
            )
                ? source.recurring
                : [],

        unusual:
            Array.isArray(
                source.unusual
            )
                ? source.unusual
                : [],

        unusual_spending:
            Array.isArray(
                source.unusual_spending
            )
                ? source.unusual_spending
                : (
                    Array.isArray(
                        source.unusual
                    )
                        ? source.unusual
                        : []
                ),

        monthly_spending:
            source.monthly_spending ||
            {},

        transactions:
            transactions,

        recent_transactions:
            Array.isArray(
                source.recent_transactions
            )
                ? source.recent_transactions.map(
                    normalizeTransaction
                )
                : transactions
                    .slice()
                    .reverse()
                    .slice(
                        0,
                        10
                    )

    };

}


/* ============================================================
   LOAD DASHBOARD DATA
   ============================================================ */

async function loadDashboardData() {

    try {

        const response =
            await fetch(
                "/api/dashboard"
            );


        const data =
            await safeJson(
                response
            );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Dashboard data could not be loaded."
            );

        }


        financialData =
            normalizeDashboardResponse(
                data
            );


        renderFinancialOverview(
            financialData
        );

        renderSpending(
            financialData
        );

        renderCategories(
            financialData
        );

        renderRecurring(
            financialData
        );

        renderUnusual(
            financialData
        );

        renderMonthlySpending(
            financialData
        );

        renderTransactions(
            financialData
        );


        if (
            financialData.transaction_count >
            0
        ) {

            setDataStatus(
                "Data loaded"
            );

        } else {

            setDataStatus(
                "No data loaded"
            );

        }

    } catch (error) {

        console.error(
            "Dashboard API error:",
            error
        );

        /*
         * Keep the default ₹0 state.
         */

        setDataStatus(
            "No data loaded"
        );

    }

}


/* ============================================================
   NORMALIZE DASHBOARD RESPONSE
   ============================================================ */

function normalizeDashboardResponse(
    data
) {

    const transactions =
        Array.isArray(
            data.transactions
        )
            ? data.transactions.map(
                normalizeTransaction
            )
            : [];


    return {

        success:
            true,

        income:
            Number(
                data.income ||
                0
            ),

        expenses:
            Number(
                data.expenses ||
                0
            ),

        savings:
            Number(
                data.savings ||
                0
            ),

        savings_rate:
            Number(
                data.savings_rate ||
                0
            ),

        transaction_count:
            Number(
                data.transaction_count ||
                transactions.length ||
                0
            ),

        category_spending:
            data.category_spending ||
            {},

        recurring:
            Array.isArray(
                data.recurring
            )
                ? data.recurring
                : [],

        unusual:
            Array.isArray(
                data.unusual
            )
                ? data.unusual
                : [],

        unusual_spending:
            Array.isArray(
                data.unusual_spending
            )
                ? data.unusual_spending
                : (
                    Array.isArray(
                        data.unusual
                    )
                        ? data.unusual
                        : []
                ),

        monthly_spending:
            data.monthly_spending ||
            {},

        transactions:
            transactions,

        recent_transactions:
            Array.isArray(
                data.recent_transactions
            )
                ? data.recent_transactions.map(
                    normalizeTransaction
                )
                : transactions
                    .slice()
                    .reverse()
                    .slice(
                        0,
                        10
                    ),

        budget_progress:
            Array.isArray(
                data.budget_progress
            )
                ? data.budget_progress
                : [],

        insights:
            Array.isArray(
                data.insights
            )
                ? data.insights
                : []

    };

}


/* ============================================================
   FINANCIAL OVERVIEW
   ============================================================ */

function renderFinancialOverview(
    data
) {

    setText(
        "incomeValue",
        formatINR(
            data.income
        )
    );


    setText(
        "expenseValue",
        formatINR(
            data.expenses
        )
    );


    setText(
        "savingsValue",
        formatINR(
            data.savings
        )
    );


    setText(
        "savingsRate",
        `${Number(
            data.savings_rate ||
            0
        ).toFixed(1)}% savings rate`
    );


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
   SPENDING DOUGHNUT CHART
   ============================================================ */

function renderSpending(
    data
) {

    const canvas =
        document.getElementById(
            "spendingChart"
        );


    if (!canvas) {
        return;
    }


    if (
        typeof Chart ===
        "undefined"
    ) {

        console.error(
            "Chart.js not loaded."
        );

        return;
    }


    const categorySpending =
        data.category_spending ||
        {};


    const entries =
        Object.entries(
            categorySpending
        )
        .filter(
            function (
                item
            ) {

                return Number(
                    item[1]
                ) > 0;

            }
        )
        .sort(
            function (
                a,
                b
            ) {

                return (
                    Number(
                        b[1]
                    ) -
                    Number(
                        a[1]
                    )
                );

            }
        );


    if (
        spendingChart
    ) {

        spendingChart.destroy();

        spendingChart =
            null;

    }


    if (!entries.length) {
        return;
    }


    const colors = [

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

                                        return colors[
                                            index %
                                            colors.length
                                        ];

                                    }
                                ),

                            borderWidth:
                                0

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

                                        return (
                                            context.label +
                                            ": " +
                                            formatINR(
                                                context.raw
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
   TOP CATEGORIES
   ============================================================ */

function renderCategories(
    data
) {

    const container =
        document.getElementById(
            "categoriesList"
        );


    if (!container) {
        return;
    }


    const entries =
        Object.entries(
            data.category_spending ||
            {}
        )
        .filter(
            function (
                item
            ) {

                return Number(
                    item[1]
                ) > 0;

            }
        )
        .sort(
            function (
                a,
                b
            ) {

                return (
                    Number(
                        b[1]
                    ) -
                    Number(
                        a[1]
                    )
                );

            }
        );


    if (!entries.length) {

        container.innerHTML = `

            <div class="empty-state">
                No spending data available.
            </div>

        `;

        return;
    }


    const maxAmount =
        Math.max.apply(
            null,
            entries.map(
                function (
                    item
                ) {

                    return Number(
                        item[1]
                    );

                }
            )
        );


    container.innerHTML =
        entries.map(
            function (
                item,
                index
            ) {

                const category =
                    item[0];

                const amount =
                    Number(
                        item[1]
                    );

                const width =
                    maxAmount > 0
                        ? (
                            amount /
                            maxAmount
                        ) * 100
                        : 0;


                return `

                    <div class="category-item">

                        <div class="category-top">

                            <span class="category-name">
                                ${escapeHTML(category)}
                            </span>

                            <strong class="category-value">
                                ${formatINR(amount)}
                            </strong>

                        </div>


                        <div class="category-bar">

                            <div
                                class="category-fill"
                                style="
                                    width:${width}%;
                                    background:${getCategoryColor(index)};
                                "
                            ></div>

                        </div>

                    </div>

                `;

            }
        ).join("");

}


/* ============================================================
   CATEGORY COLOR
   ============================================================ */

function getCategoryColor(
    index
) {

    const colors = [

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


    return colors[
        index %
        colors.length
    ];

}


/* ============================================================
   RECURRING PAYMENTS
   ============================================================ */

function renderRecurring(
    data
) {

    const container =
        document.getElementById(
            "recurringList"
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

            <div class="empty-state">
                No recurring payments detected.
            </div>

        `;

        return;
    }


    container.innerHTML =
        recurring.map(
            function (
                item
            ) {

                return `

                    <div class="recurring-item">

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
        ).join("");

}


/* ============================================================
   UNUSUAL SPENDING
   ============================================================ */

function renderUnusual(
    data
) {

    const container =
        document.getElementById(
            "unusualList"
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

            <div class="empty-state">
                No unusual spending detected.
            </div>

        `;

        return;
    }


    container.innerHTML =
        unusual.map(
            function (
                item
            ) {

                const amount =
                    Math.abs(
                        Number(
                            item.amount ||
                            0
                        )
                    );


                return `

                    <div class="unusual-item">

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

                                ${
                                    item.average !==
                                    undefined
                                        ? " · Average: " +
                                          formatINR(
                                              item.average
                                          )
                                        : ""
                                }

                            </span>

                        </div>


                        <strong>
                            ${formatINR(amount)}
                        </strong>

                    </div>

                `;

            }
        ).join("");

}


/* ============================================================
   MONTHLY SPENDING
   ============================================================ */

function renderMonthlySpending(
    data
) {

    const container =
        document.getElementById(
            "monthlySpending"
        );


    if (!container) {
        return;
    }


    const entries =
        Object.entries(
            data.monthly_spending ||
            {}
        )
        .sort(
            function (
                a,
                b
            ) {

                return (
                    a[0].localeCompare(
                        b[0]
                    )
                );

            }
        );


    if (!entries.length) {

        container.innerHTML = `

            <div class="empty-state">
                No monthly data available.
            </div>

        `;

        return;
    }


    const maximum =
        Math.max.apply(
            null,
            entries.map(
                function (
                    item
                ) {

                    return Number(
                        item[1]
                    );

                }
            )
        );


    container.innerHTML =
        entries.map(
            function (
                item
            ) {

                const month =
                    item[0];

                const amount =
                    Number(
                        item[1]
                    );

                const width =
                    maximum > 0
                        ? (
                            amount /
                            maximum
                        ) * 100
                        : 0;


                return `

                    <div class="monthly-item">

                        <div class="monthly-header">

                            <span>
                                ${escapeHTML(month)}
                            </span>

                            <strong>
                                ${formatINR(amount)}
                            </strong>

                        </div>


                        <div class="monthly-bar">

                            <div
                                class="monthly-fill"
                                style="
                                    width:${width}%;
                                "
                            ></div>

                        </div>

                    </div>

                `;

            }
        ).join("");

}


/* ============================================================
   RECENT TRANSACTIONS
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

            <div class="empty-state">
                No transactions available.
            </div>

        `;

        return;
    }


    container.innerHTML =
        transactions.map(
            function (
                transaction
            ) {

                const tx =
                    normalizeTransaction(
                        transaction
                    );


                const isIncome =
                    tx.amount > 0;


                return `

                    <div class="transaction-row">

                        <div class="transaction-date">
                            ${
                                escapeHTML(
                                    tx.date
                                )
                            }
                        </div>


                        <div class="transaction-description">

                            ${
                                escapeHTML(
                                    tx.description
                                )
                            }

                        </div>


                        <div class="transaction-category">

                            ${
                                escapeHTML(
                                    tx.category
                                )
                            }

                        </div>


                        <div class="
                            transaction-amount
                            ${
                                isIncome
                                    ? "income"
                                    : "expense"
                            }
                        ">

                            ${
                                isIncome
                                    ? "+"
                                    : "-"
                            }

                            ${
                                formatINR(
                                    Math.abs(
                                        tx.amount
                                    )
                                )
                            }

                        </div>

                    </div>

                `;

            }
        ).join("");

}


/* ============================================================
   NORMALIZE TRANSACTION
   ============================================================ */

function normalizeTransaction(
    tx
) {

    tx =
        tx &&
        typeof tx === "object"
            ? tx
            : {};


    let amount =
        Number(
            tx.amount ??
            tx.Amount ??
            0
        );


    const type =
        String(
            tx.type ||
            tx.transaction_type ||
            ""
        )
        .toLowerCase();


    /*
     * Database stores expense type
     * separately.
     */

    if (
        type === "expense"
    ) {

        amount =
            -Math.abs(
                amount
            );

    } else if (
        type === "income"
    ) {

        amount =
            Math.abs(
                amount
            );

    }


    return {

        id:
            tx.id ||
            null,

        date:
            tx.date ||
            tx.Date ||
            "",

        description:
            tx.description ||
            tx.Description ||
            "Unknown transaction",

        amount:
            amount,

        category:
            tx.category ||
            tx.Category ||
            "Other"

    };

}


/* ============================================================
   GOAL IMPACT
   ============================================================ */

async function loadGoalImpact() {

    const container =
        document.getElementById(
            "goalImpact"
        );


    if (!container) {
        return;
    }


    try {

        const response =
            await fetch(
                "/api/goal-impact"
            );


        const data =
            await safeJson(
                response
            );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Goal impact unavailable."
            );

        }


        const goals =
            Array.isArray(
                data.goals
            )
                ? data.goals
                : [];


        if (!goals.length) {

            container.innerHTML = `

                <div class="empty-state">
                    No financial goals created yet.
                </div>

            `;

            return;
        }


        container.innerHTML =
            goals.map(
                function (
                    goal
                ) {

                    const progress =
                        Number(
                            goal.progress ||
                            0
                        );


                    return `

                        <div class="goal-impact-card">

                            <div class="goal-impact-top">

                                <div>

                                    <strong>
                                        ${
                                            escapeHTML(
                                                goal.name ||
                                                "Financial Goal"
                                            )
                                        }
                                    </strong>

                                    <span>
                                        Target:
                                        ${
                                            formatINR(
                                                goal.target_amount
                                            )
                                        }
                                    </span>

                                </div>


                                <strong>
                                    ${progress.toFixed(1)}%
                                </strong>

                            </div>


                            <div class="progress-bar">

                                <div
                                    class="progress-value"
                                    style="
                                        width:${Math.min(
                                            progress,
                                            100
                                        )}%
                                    "
                                ></div>

                            </div>


                            <div class="goal-impact-bottom">

                                <span>
                                    Remaining:
                                    ${
                                        formatINR(
                                            goal.remaining_amount
                                        )
                                    }
                                </span>

                                <span>
                                    Monthly savings:
                                    ${
                                        formatINR(
                                            goal.monthly_savings
                                        )
                                    }
                                </span>

                            </div>

                        </div>

                    `;

                }
            ).join("");

    } catch (error) {

        console.error(
            "Goal impact error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">
                Goal impact could not be loaded.
            </div>

        `;

    }

}


/* ============================================================
   BUDGET ANALYSIS
   ============================================================ */

async function loadBudgetAnalysis() {

    const container =
        document.getElementById(
            "budgetAnalysis"
        );


    if (!container) {
        return;
    }


    try {

        const response =
            await fetch(
                "/api/budget-analysis"
            );


        const data =
            await safeJson(
                response
            );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Budget analysis unavailable."
            );

        }


        const budgets =
            Array.isArray(
                data.budgets
            )
                ? data.budgets
                : [];


        if (!budgets.length) {

            container.innerHTML = `

                <div class="empty-state">
                    No budgets created yet.
                </div>

            `;

            return;
        }


        container.innerHTML =
            budgets.map(
                function (
                    budget
                ) {

                    const usedPercent =
                        Number(
                            budget.used_percent ||
                            0
                        );


                    const status =
                        budget.status ||
                        "healthy";


                    return `

                        <div class="
                            budget-analysis-item
                            ${escapeHTML(status)}
                        ">

                            <div class="budget-analysis-top">

                                <div>

                                    <strong>
                                        ${
                                            escapeHTML(
                                                budget.category
                                            )
                                        }
                                    </strong>

                                    <span>
                                        ${
                                            formatINR(
                                                budget.actual
                                            )
                                        }
                                        /
                                        ${
                                            formatINR(
                                                budget.budget
                                            )
                                        }
                                    </span>

                                </div>


                                <strong>
                                    ${usedPercent.toFixed(1)}%
                                </strong>

                            </div>


                            <div class="progress-bar">

                                <div
                                    class="progress-value"
                                    style="
                                        width:${Math.min(
                                            usedPercent,
                                            100
                                        )}%
                                    "
                                ></div>

                            </div>


                            <div class="budget-analysis-bottom">

                                <span>
                                    Remaining:
                                    ${
                                        formatINR(
                                            Math.max(
                                                Number(
                                                    budget.remaining ||
                                                    0
                                                ),
                                                0
                                            )
                                        )
                                    }
                                </span>

                                <span>
                                    ${
                                        getBudgetStatusLabel(
                                            status
                                        )
                                    }
                                </span>

                            </div>

                        </div>

                    `;

                }
            ).join("");

    } catch (error) {

        console.error(
            "Budget analysis error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">
                Budget analysis could not be loaded.
            </div>

        `;

    }

}


/* ============================================================
   BUDGET STATUS
   ============================================================ */

function getBudgetStatusLabel(
    status
) {

    if (
        status ===
        "over"
    ) {

        return "Over budget";

    }


    if (
        status ===
        "warning"
    ) {

        return "Near limit";

    }


    return "Within budget";

}


/* ============================================================
   AI RESULT
   ============================================================ */

function showAIResult(
    message,
    isError = false
) {

    const result =
        document.getElementById(
            "aiResult"
        );


    const resultText =
        document.getElementById(
            "aiResultText"
        );


    if (!result) {
        return;
    }


    result.style.display =
        "flex";


    if (resultText) {

        resultText.textContent =
            message;

    }


    result.classList.toggle(
        "error",
        Boolean(
            isError
        )
    );

}


/* ============================================================
   AUTONOMOUS AGENT
   ============================================================ */

async function runAutonomousAgent() {

    if (!financialData) {
        return;
    }


    try {

        const response =
            await fetch(
                "/agent/analyze",
                {

                    method:
                        "POST",

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

            /*
             * Agent failure should not break
             * financial dashboard.
             */

            console.warn(
                "Agent analysis failed:",
                data.error
            );

            return;
        }


        const agentMessage =
            getAgentMessage(
                data
            );


        if (
            agentMessage
        ) {

            showAIResult(
                agentMessage
            );

        }

    } catch (error) {

        console.warn(
            "Autonomous agent unavailable:",
            error.message
        );

    }

}


/* ============================================================
   AGENT MESSAGE EXTRACTION
   ============================================================ */

function getAgentMessage(
    data
) {

    if (!data) {
        return "";
    }


    if (
        typeof data.message ===
        "string"
    ) {

        return data.message;

    }


    if (
        typeof data.summary ===
        "string"
    ) {

        return data.summary;

    }


    if (
        data.report &&
        typeof data.report.summary ===
        "string"
    ) {

        return data.report.summary;

    }


    if (
        data.report &&
        typeof data.report.headline ===
        "string"
    ) {

        return data.report.headline;

    }


    return "";

}


/* ============================================================
   ASSISTANT SETUP
   ============================================================ */

function setupAssistant() {

    const input =
        document.getElementById(
            "assistantInput"
        );


    if (!input) {
        return;
    }


    input.addEventListener(
        "keydown",
        function (
            event
        ) {

            if (
                event.key ===
                "Enter"
            ) {

                event.preventDefault();

                askFinPilot();

            }

        }
    );

}


/* ============================================================
   QUICK QUESTIONS
   ============================================================ */

function setupQuickQuestions() {

    const buttons =
        document.querySelectorAll(
            ".quick-question"
        );


    buttons.forEach(
        function (
            button
        ) {

            button.addEventListener(
                "click",
                function () {

                    const question =
                        button.dataset.question ||
                        button.textContent.trim();


                    const input =
                        document.getElementById(
                            "assistantInput"
                        );


                    if (!input) {
                        return;
                    }


                    input.value =
                        question;

                    input.focus();

                    askFinPilot();

                }
            );

        }
    );

}


/* ============================================================
   ASK FINPILOT
   ============================================================ */

async function askFinPilot() {

    const input =
        document.getElementById(
            "assistantInput"
        );


    const messages =
        document.getElementById(
            "assistantMessages"
        );


    if (
        !input ||
        !messages
    ) {

        return;

    }


    const question =
        input.value.trim();


    if (!question) {
        return;
    }


    appendChatMessage(
        messages,
        question,
        "user"
    );


    input.value =
        "";


    const loadingBubble =
        appendChatMessage(
            messages,
            "FinPilot is thinking...",
            "assistant"
        );


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
                "FinPilot could not answer."
            );

        }


        const answer =
            data.answer ||
            data.message ||
            data.response ||
            "No answer returned.";


        if (loadingBubble) {

            loadingBubble.textContent =
                answer;

        }

    } catch (error) {

        if (loadingBubble) {

            loadingBubble.textContent =
                error.message ||
                "Something went wrong.";

        }

    }

}


/* ============================================================
   APPEND CHAT MESSAGE
   ============================================================ */

function appendChatMessage(
    container,
    message,
    type
) {

    const wrapper =
        document.createElement(
            "div"
        );


    if (
        type ===
        "user"
    ) {

        wrapper.className =
            "user-message";


        wrapper.innerHTML = `

            <div class="message-bubble user-bubble">
                ${escapeHTML(message)}
            </div>

        `;

    } else {

        wrapper.className =
            "assistant-message";


        wrapper.innerHTML = `

            <div class="message-avatar">
                ✦
            </div>

            <div class="message-bubble">
                ${escapeHTML(message)}
            </div>

        `;

    }


    container.appendChild(
        wrapper
    );


    container.scrollTop =
        container.scrollHeight;


    return wrapper.querySelector(
        ".message-bubble"
    );

}


/* ============================================================
   DATA STATUS
   ============================================================ */

function setDataStatus(
    value
) {

    const element =
        document.getElementById(
            "dataStatus"
        );


    if (element) {

        element.textContent =
            value;

    }

}


/* ============================================================
   UPLOAD STATUS
   ============================================================ */

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


    element.innerHTML = `

        <span class="status-line"></span>

        ${escapeHTML(message)}

    `;


    element.classList.toggle(
        "error",
        Boolean(
            isError
        )
    );

}


/* ============================================================
   TEXT
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


/* ============================================================
   FORMAT INR
   ============================================================ */

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
                minimumFractionDigits:
                    0,

                maximumFractionDigits:
                    2
            }
        )
    );

}


/* ============================================================
   HTML ESCAPE
   ============================================================ */

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


/* ============================================================
   SAFE JSON
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
   GLOBAL FUNCTIONS
   Required by dashboard.html onclick=""
   ============================================================ */

window.uploadStatement =
    uploadStatement;

window.askFinPilot =
    askFinPilot;

window.loadDashboardData =
    loadDashboardData;

window.loadGoalImpact =
    loadGoalImpact;

window.loadBudgetAnalysis =
    loadBudgetAnalysis;