/* =========================================================
   FINPILOT DASHBOARD
   Colourful Charts + Dashboard + AI Assistant
   ========================================================= */

let spendingChart = null;


/* =========================================================
   COLOUR PALETTE
   ========================================================= */

const categoryColors = [
    "#4F46E5", // Indigo
    "#7C3AED", // Purple
    "#F97316", // Orange
    "#EC4899", // Pink
    "#10B981", // Green
    "#F59E0B", // Amber
    "#06B6D4", // Cyan
    "#EF4444", // Red
    "#8B5CF6", // Violet
    "#14B8A6"  // Teal
];


/* =========================================================
   HELPERS
   ========================================================= */

function formatMoney(value) {

    const amount = Number(value || 0);

    return "₹" + amount.toLocaleString("en-IN", {
        maximumFractionDigits: 0
    });

}


function escapeHtml(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


function getElement(...ids) {

    for (const id of ids) {

        const element =
            document.getElementById(id);

        if (element) {
            return element;
        }

    }

    return null;

}


/* =========================================================
   LOAD DASHBOARD
   ========================================================= */

async function loadDashboard() {

    try {

        console.log("FinPilot: Loading dashboard...");

        const response =
            await fetch("/api/dashboard");

        if (!response.ok) {

            throw new Error(
                `Dashboard API returned ${response.status}`
            );

        }

        const data =
            await response.json();

        console.log(
            "FinPilot dashboard data:",
            data
        );

        renderDashboard(data);

        loadGoalImpact();

        loadBudgetAnalysis();

    } catch (error) {

        console.error(
            "Dashboard loading error:",
            error
        );

        showDashboardError(
            error.message
        );

    }

}


/* =========================================================
   RENDER DASHBOARD
   ========================================================= */

function renderDashboard(data) {

    if (!data) {
        return;
    }


    /* ================= SUMMARY ================= */

    const income =
        Number(data.income || 0);

    const expenses =
        Number(data.expenses || 0);

    const savings =
        Number(
            data.savings !== undefined
                ? data.savings
                : income - expenses
        );

    const savingsRate =
        Number(data.savings_rate || 0);

    const transactions =
        Array.isArray(data.transactions)
            ? data.transactions
            : [];

    const transactionCount =
        Number(
            data.transaction_count !== undefined
                ? data.transaction_count
                : transactions.length
        );


    const incomeElement =
        getElement("incomeValue");

    const expenseElement =
        getElement("expenseValue");

    const savingsElement =
        getElement("savingsValue");

    const countElement =
        getElement("transactionCount");

    const savingsRateElement =
        getElement("savingsRate");


    if (incomeElement) {

        incomeElement.textContent =
            formatMoney(income);

    }

    if (expenseElement) {

        expenseElement.textContent =
            formatMoney(expenses);

    }

    if (savingsElement) {

        savingsElement.textContent =
            formatMoney(savings);

    }

    if (countElement) {

        countElement.textContent =
            transactionCount;

    }

    if (savingsRateElement) {

        savingsRateElement.textContent =
            `${savingsRate.toFixed(1)}% savings rate`;

    }


    /* ================= CATEGORIES ================= */

    renderCategories(
        data.category_spending || {}
    );


    /* ================= CHART ================= */

    renderSpendingChart(
        data.category_spending || {}
    );


    /* ================= RECURRING ================= */

    renderRecurring(
        data.recurring || []
    );


    /* ================= UNUSUAL ================= */

    renderUnusual(
        data.unusual || []
    );


    /* ================= MONTHLY ================= */

    renderMonthly(
        data.monthly_spending || {}
    );


    /* ================= RECENT ================= */

    renderRecentTransactions(
        transactions
    );

}


/* =========================================================
   COLOURFUL DOUGHNUT CHART
   ========================================================= */

function renderSpendingChart(categoryData) {

    const canvas =
        document.getElementById(
            "spendingChart"
        );

    if (!canvas) {
        return;
    }


    if (
        typeof Chart === "undefined"
    ) {

        console.error(
            "Chart.js is not loaded."
        );

        return;

    }


    const entries =
        Object.entries(
            categoryData || {}
        )
        .filter(
            ([, value]) =>
                Number(value) > 0
        )
        .sort(
            (a, b) =>
                Number(b[1]) - Number(a[1])
        );


    if (spendingChart) {

        spendingChart.destroy();

        spendingChart = null;

    }


    if (!entries.length) {

        return;

    }


    const labels =
        entries.map(
            ([category]) =>
                category
        );


    const values =
        entries.map(
            ([, amount]) =>
                Number(amount)
        );


    const chartColors =
        entries.map(
            (_, index) =>
                categoryColors[
                    index %
                    categoryColors.length
                ]
        );


    const ctx =
        canvas.getContext("2d");


    spendingChart =
        new Chart(
            ctx,
            {
                type: "doughnut",

                data: {

                    labels: labels,

                    datasets: [

                        {

                            data: values,

                            backgroundColor:
                                chartColors,

                            borderColor:
                                "#ffffff",

                            borderWidth:
                                3,

                            hoverBorderColor:
                                "#ffffff",

                            hoverOffset:
                                8

                        }

                    ]

                },

                options: {

                    responsive: true,

                    maintainAspectRatio: false,

                    cutout: "64%",

                    animation: {

                        animateRotate: true,

                        animateScale: true,

                        duration: 900

                    },

                    plugins: {

                        legend: {

                            position: "bottom",

                            labels: {

                                usePointStyle: true,

                                pointStyle: "circle",

                                padding: 18,

                                color: "#374151",

                                font: {

                                    size: 11,

                                    weight: "600"

                                }

                            }

                        },

                        tooltip: {

                            callbacks: {

                                label: function(context) {

                                    const value =
                                        Number(
                                            context.raw || 0
                                        );

                                    const total =
                                        values.reduce(
                                            (
                                                sum,
                                                number
                                            ) =>
                                                sum +
                                                number,
                                            0
                                        );

                                    const percentage =
                                        total > 0
                                            ? (
                                                value /
                                                total
                                            ) * 100
                                            : 0;

                                    return (
                                        ` ${context.label}: ` +
                                        formatMoney(value) +
                                        ` (${percentage.toFixed(1)}%)`
                                    );

                                }

                            }

                        }

                    }

                }

            }
        );

}


/* =========================================================
   COLOURFUL TOP CATEGORIES
   ========================================================= */

function renderCategories(categoryData) {

    const container =
        getElement(
            "categoriesList"
        );


    if (!container) {
        return;
    }


    const entries =
        Object.entries(
            categoryData || {}
        )
        .filter(
            ([, amount]) =>
                Number(amount) > 0
        )
        .sort(
            (a, b) =>
                Number(b[1]) - Number(a[1])
        );


    if (!entries.length) {

        container.innerHTML = `

            <div class="empty-state">

                No spending data available.

            </div>

        `;

        return;

    }


    const total =
        entries.reduce(
            (
                sum,
                [, amount]
            ) =>
                sum +
                Number(amount),
            0
        );


    const topCategories =
        entries.slice(0, 7);


    container.innerHTML =
        topCategories
            .map(
                (
                    [category, amount],
                    index
                ) => {

                    const percentage =
                        total > 0
                            ? (
                                Number(amount) /
                                total
                            ) * 100
                            : 0;


                    const color =
                        categoryColors[
                            index %
                            categoryColors.length
                        ];


                    return `

                        <div
                            class="category-item"
                            style="
                                padding:12px;
                                border-radius:12px;
                                background:#fafafa;
                                border:1px solid #eef0f3;
                            ">

                            <div class="category-info">

                                <strong>
                                    ${escapeHtml(category)}
                                </strong>

                                <span>
                                    ${percentage.toFixed(1)}%
                                </span>

                            </div>


                            <div
                                class="category-bar"
                                style="
                                    height:9px;
                                    margin-top:8px;
                                ">

                                <div
                                    class="category-fill"
                                    style="
                                        width:${percentage}%;
                                        background:${color};
                                    ">
                                </div>

                            </div>


                            <div
                                class="category-amount"
                                style="
                                    margin-top:6px;
                                ">

                                ${formatMoney(amount)}

                            </div>

                        </div>

                    `;

                }
            )
            .join("");

}


/* =========================================================
   RECURRING PAYMENTS
   ========================================================= */

function renderRecurring(recurring) {

    const container =
        getElement(
            "recurringList"
        );


    if (!container) {
        return;
    }


    if (
        !Array.isArray(recurring) ||
        recurring.length === 0
    ) {

        container.innerHTML = `

            <div class="empty-state">

                No recurring payments detected.

            </div>

        `;

        return;

    }


    container.innerHTML =
        recurring
            .slice(0, 8)
            .map(
                (
                    item,
                    index
                ) => {

                    const description =
                        item.description ||
                        item.name ||
                        item.merchant ||
                        "Recurring Payment";


                    const amount =
                        Number(
                            item.amount ||
                            item.total ||
                            0
                        );


                    const count =
                        item.payments ||
                        item.count ||
                        item.frequency ||
                        "";


                    const color =
                        categoryColors[
                            index %
                            categoryColors.length
                        ];


                    return `

                        <div
                            class="recurring-item"
                            style="
                                border-left:4px solid ${color};
                            ">

                            <div>

                                <strong>
                                    ${escapeHtml(description)}
                                </strong>

                                <span>
                                    ${
                                        count
                                            ? `${escapeHtml(String(count))} payments`
                                            : "Repeated transaction"
                                    }
                                </span>

                            </div>

                            <div class="recurring-amount">

                                ${formatMoney(Math.abs(amount))}

                            </div>

                        </div>

                    `;

                }
            )
            .join("");

}


/* =========================================================
   UNUSUAL SPENDING
   ========================================================= */

function renderUnusual(unusual) {

    const container =
        getElement(
            "unusualList"
        );


    if (!container) {
        return;
    }


    if (
        !Array.isArray(unusual) ||
        unusual.length === 0
    ) {

        container.innerHTML = `

            <div class="empty-state">

                No unusual spending detected.

            </div>

        `;

        return;

    }


    container.innerHTML =
        unusual
            .slice(0, 8)
            .map(item => {

                const description =
                    item.description ||
                    item.name ||
                    item.Description ||
                    "Unusual transaction";


                const amount =
                    Number(
                        item.amount ||
                        item.Amount ||
                        0
                    );


                const reason =
                    item.reason ||
                    item.category ||
                    "This transaction stands out from normal spending.";


                return `

                    <div class="unusual-item">

                        <strong>

                            ${escapeHtml(description)}

                            —
                            ${formatMoney(
                                Math.abs(amount)
                            )}

                        </strong>


                        <p>

                            ${escapeHtml(reason)}

                        </p>

                    </div>

                `;

            })
            .join("");

}


/* =========================================================
   COLOURFUL MONTHLY SPENDING
   ========================================================= */

function renderMonthly(monthlyData) {

    const container =
        getElement(
            "monthlySpending"
        );


    if (!container) {
        return;
    }


    const entries =
        Object.entries(
            monthlyData || {}
        )
        .sort(
            (a, b) =>
                String(a[0]).localeCompare(
                    String(b[0])
                )
        );


    if (!entries.length) {

        container.innerHTML = `

            <div class="empty-state">

                No monthly data available.

            </div>

        `;

        return;

    }


    const maxValue =
        Math.max(
            ...entries.map(
                ([, value]) =>
                    Number(value) || 0
            )
        );


    container.innerHTML =
        entries
            .map(
                (
                    [month, amount],
                    index
                ) => {

                    const value =
                        Number(amount) || 0;


                    const percentage =
                        maxValue > 0
                            ? (
                                value /
                                maxValue
                            ) * 100
                            : 0;


                    const color =
                        categoryColors[
                            index %
                            categoryColors.length
                        ];


                    return `

                        <div class="monthly-item">

                            <strong>
                                ${escapeHtml(month)}
                            </strong>


                            <div
                                class="monthly-bar"
                                style="
                                    background:#eef2f7;
                                ">

                                <div
                                    class="monthly-fill"
                                    style="
                                        width:${percentage}%;
                                        background:${color};
                                    ">
                                </div>

                            </div>


                            <div class="monthly-amount">

                                ${formatMoney(value)}

                            </div>

                        </div>

                    `;

                }
            )
            .join("");

}


/* =========================================================
   RECENT TRANSACTIONS
   ========================================================= */

function renderRecentTransactions(transactions) {

    const container =
        getElement(
            "recentTransactions"
        );


    if (!container) {
        return;
    }


    if (
        !Array.isArray(transactions) ||
        transactions.length === 0
    ) {

        container.innerHTML = `

            <div class="empty-state">

                No transactions available.

            </div>

        `;

        return;

    }


    const sorted =
        [...transactions]
            .sort(
                (a, b) =>
                    String(
                        b.date || ""
                    ).localeCompare(
                        String(
                            a.date || ""
                        )
                    )
            )
            .slice(0, 8);


    container.innerHTML =
        sorted
            .map(
                (
                    transaction,
                    index
                ) => {

                    const description =
                        transaction.description ||
                        "Transaction";


                    const category =
                        transaction.category ||
                        "Other";


                    const transactionDate =
                        transaction.date ||
                        "";


                    const rawAmount =
                        Number(
                            transaction.amount || 0
                        );


                    const type =
                        String(
                            transaction.transaction_type ||
                            transaction.type ||
                            ""
                        ).toLowerCase();


                    const isIncome =
                        type === "income" ||
                        rawAmount > 0;


                    const amount =
                        Math.abs(rawAmount);


                    const indicatorColor =
                        isIncome
                            ? "#10B981"
                            : categoryColors[
                                index %
                                categoryColors.length
                              ];


                    return `

                        <div
                            class="recent-transaction"
                            style="
                                border-left:3px solid ${indicatorColor};
                                padding-left:10px;
                            ">

                            <div>

                                <strong>

                                    ${escapeHtml(
                                        description
                                    )}

                                </strong>

                                <span>

                                    ${escapeHtml(
                                        category
                                    )}

                                    ·

                                    ${escapeHtml(
                                        transactionDate
                                    )}

                                </span>

                            </div>


                            <div>

                                <span>

                                    ${
                                        isIncome
                                            ? "Income"
                                            : "Expense"
                                    }

                                </span>

                            </div>


                            <div
                                class="transaction-amount ${
                                    isIncome
                                        ? "transaction-income"
                                        : "transaction-expense"
                                }">

                                ${
                                    isIncome
                                        ? "+"
                                        : "-"
                                }

                                ${formatMoney(amount)}

                            </div>

                        </div>

                    `;

                }
            )
            .join("");

}


/* =========================================================
   GOAL IMPACT
   ========================================================= */

async function loadGoalImpact() {

    const container =
        getElement(
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


        if (!response.ok) {

            throw new Error(
                "Unable to load goal impact."
            );

        }


        const data =
            await response.json();


        renderGoalImpact(
            data
        );


    } catch (error) {

        console.error(
            "Goal impact error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">

                Goal impact is unavailable right now.

            </div>

        `;

    }

}


/* =========================================================
   RENDER GOAL IMPACT
   ========================================================= */

function renderGoalImpact(data) {

    const container =
        getElement(
            "goalImpact"
        );


    if (!container) {
        return;
    }


    const goals =
        data.goals ||
        [];


    if (
        !Array.isArray(goals) ||
        goals.length === 0
    ) {

        container.innerHTML = `

            <div class="empty-state">

                No financial goals available.

            </div>

        `;

        return;

    }


    container.innerHTML =
        goals
            .map(
                (
                    goal,
                    index
                ) => {

                    const name =
                        goal.name ||
                        "Financial Goal";


                    const target =
                        Number(
                            goal.target_amount ||
                            goal.target ||
                            0
                        );


                    const current =
                        Number(
                            goal.current_amount ||
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


                    const color =
                        categoryColors[
                            index %
                            categoryColors.length
                        ];


                    return `

                        <div
                            class="goal-impact-card"
                            style="
                                border-top:4px solid ${color};
                            ">

                            <h3>

                                ${escapeHtml(name)}

                            </h3>


                            <p>

                                ${formatMoney(current)}
                                /
                                ${formatMoney(target)}

                            </p>


                            <div class="goal-progress">

                                <div
                                    class="goal-progress-fill"
                                    style="
                                        width:${percentage}%;
                                        background:${color};
                                    ">
                                </div>

                            </div>


                            <p>

                                ${percentage.toFixed(0)}%
                                completed

                            </p>

                        </div>

                    `;

                }
            )
            .join("");

}


/* =========================================================
   BUDGET ANALYSIS
   ========================================================= */

async function loadBudgetAnalysis() {

    const container =
        getElement(
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


        if (!response.ok) {

            throw new Error(
                "Unable to load budget analysis."
            );

        }


        const data =
            await response.json();


        renderBudgetAnalysis(
            data
        );


    } catch (error) {

        console.error(
            "Budget analysis error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">

                Budget analysis is unavailable right now.

            </div>

        `;

    }

}


/* =========================================================
   RENDER BUDGET ANALYSIS
   ========================================================= */

function renderBudgetAnalysis(data) {

    const container =
        getElement(
            "budgetAnalysis"
        );


    if (!container) {
        return;
    }


    const budgets =
        data.budgets ||
        [];


    if (
        !Array.isArray(budgets) ||
        budgets.length === 0
    ) {

        container.innerHTML = `

            <div class="empty-state">

                No budgets created yet.

            </div>

        `;

        return;

    }


    container.innerHTML =
        budgets
            .map(
                (
                    item,
                    index
                ) => {

                    const category =
                        item.category ||
                        "Other";


                    const budget =
                        Number(
                            item.budget ||
                            item.amount ||
                            item.budget_amount ||
                            0
                        );


                    const actual =
                        Number(
                            item.actual ||
                            item.spent ||
                            item.actual_amount ||
                            0
                        );


                    const percentage =
                        budget > 0
                            ? Math.min(
                                (
                                    actual /
                                    budget
                                ) * 100,
                                100
                            )
                            : 0;


                    let status =
                        "Within Budget";


                    let statusColor =
                        "#10B981";


                    if (
                        actual >
                        budget
                    ) {

                        status =
                            "Over Budget";

                        statusColor =
                            "#EF4444";

                    } else if (
                        budget > 0 &&
                        actual >=
                        budget * 0.8
                    ) {

                        status =
                            "Near Limit";

                        statusColor =
                            "#F59E0B";

                    }


                    const barColor =
                        categoryColors[
                            index %
                            categoryColors.length
                        ];


                    return `

                        <div
                            class="budget-analysis-item"
                            style="
                                border-left:4px solid ${statusColor};
                            ">

                            <strong>

                                ${escapeHtml(category)}

                            </strong>


                            <div>

                                <span>

                                    ${formatMoney(actual)}
                                    /
                                    ${formatMoney(budget)}

                                </span>


                                <div class="budget-progress">

                                    <div
                                        class="budget-progress-fill"
                                        style="
                                            width:${percentage}%;
                                            background:${barColor};
                                        ">
                                    </div>

                                </div>

                            </div>


                            <div
                                class="budget-status"
                                style="
                                    color:${statusColor};
                                ">

                                ${status}

                            </div>

                        </div>

                    `;

                }
            )
            .join("");

}


/* =========================================================
   UPLOAD STATEMENT
   ========================================================= */

async function uploadStatement() {

    const input =
        document.getElementById(
            "fileInput"
        );


    const button =
        getElement(
            "uploadBtn"
        );


    if (
        !input ||
        !input.files ||
        input.files.length === 0
    ) {

        alert(
            "Please choose a file first."
        );

        return;

    }


    const file =
        input.files[0];


    const formData =
        new FormData();


    formData.append(
        "file",
        file
    );


    if (button) {

        button.disabled = true;

        button.textContent =
            "Analyzing...";

    }


    try {

        const response =
            await fetch(
                "/upload",
                {
                    method: "POST",
                    body: formData
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "Upload failed."
            );

        }


        const resultBox =
            getElement(
                "aiResult"
            );


        const resultText =
            getElement(
                "aiResultText"
            );


        if (resultBox) {

            resultBox.style.display =
                "flex";

        }


        if (resultText) {

            resultText.textContent =
                result.message ||
                "Statement analyzed successfully.";

        }


        await loadDashboard();


    } catch (error) {

        console.error(
            "Upload error:",
            error
        );


        alert(
            error.message ||
            "Unable to analyze statement."
        );

    } finally {

        if (button) {

            button.disabled = false;

            button.textContent =
                "Analyze Statement";

        }

    }

}


/* =========================================================
   FILE PICKER
   ========================================================= */

function setupFilePicker() {

    const input =
        document.getElementById(
            "fileInput"
        );


    const selectedFile =
        getElement(
            "selectedFile"
        );


    if (!input) {
        return;
    }


    input.addEventListener(
        "change",
        function() {

            if (
                !this.files ||
                !this.files.length
            ) {

                if (selectedFile) {

                    selectedFile.style.display =
                        "none";

                }

                return;

            }


            const file =
                this.files[0];


            if (selectedFile) {

                selectedFile.style.display =
                    "block";


                selectedFile.innerHTML = `

                    Selected file:

                    <strong>
                        ${escapeHtml(file.name)}
                    </strong>

                `;

            }

        }
    );

}


/* =========================================================
   AI ASSISTANT
   ========================================================= */

async function askFinPilot() {

    const input =
        document.getElementById(
            "assistantInput"
        );


    if (!input) {
        return;
    }


    const question =
        input.value.trim();


    if (!question) {
        return;
    }


    addUserMessage(
        question
    );


    input.value = "";


    const loadingId =
        addAssistantMessage(
            "Thinking..."
        );


    try {

        const response =
            await fetch(
                "/api/agent",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            message: question
                        })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Assistant request failed."
            );

        }


        removeAssistantMessage(
            loadingId
        );


        addAssistantMessage(
            data.message ||
            "I couldn't find an answer."
        );


        if (
            data.requires_confirmation &&
            data.action
        ) {

            addConfirmationButton(
                data.action
            );

        }


    } catch (error) {

        console.error(
            "AI assistant error:",
            error
        );


        removeAssistantMessage(
            loadingId
        );


        addAssistantMessage(
            "Sorry, I couldn't process that request right now."
        );

    }

}


/* =========================================================
   QUICK QUESTION
   ========================================================= */

function askQuickQuestion(question) {

    const input =
        document.getElementById(
            "assistantInput"
        );


    if (!input) {
        return;
    }


    input.value =
        question;


    askFinPilot();

}


/* =========================================================
   USER MESSAGE
   ========================================================= */

function addUserMessage(message) {

    const container =
        getElement(
            "assistantMessages"
        );


    if (!container) {
        return;
    }


    const element =
        document.createElement(
            "div"
        );


    element.className =
        "assistant-message user-message";


    element.innerHTML = `

        <div class="message-bubble">

            ${escapeHtml(message)}

        </div>

    `;


    container.appendChild(
        element
    );


    container.scrollTop =
        container.scrollHeight;

}


/* =========================================================
   ASSISTANT MESSAGE
   ========================================================= */

function addAssistantMessage(message) {

    const container =
        getElement(
            "assistantMessages"
        );


    if (!container) {
        return null;
    }


    const id =
        "assistant-" +
        Date.now();


    const element =
        document.createElement(
            "div"
        );


    element.id =
        id;


    element.className =
        "assistant-message";


    element.innerHTML = `

        <div class="message-avatar">

            ✦

        </div>

        <div class="message-bubble">

            ${escapeHtml(message)}

        </div>

    `;


    container.appendChild(
        element
    );


    container.scrollTop =
        container.scrollHeight;


    return id;

}


/* =========================================================
   REMOVE MESSAGE
   ========================================================= */

function removeAssistantMessage(id) {

    if (!id) {
        return;
    }


    const element =
        document.getElementById(id);


    if (element) {

        element.remove();

    }

}


/* =========================================================
   CONFIRMATION BUTTON
   ========================================================= */

function addConfirmationButton(action) {

    const container =
        getElement(
            "assistantMessages"
        );


    if (!container) {
        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );


    wrapper.className =
        "assistant-message";


    wrapper.innerHTML = `

        <div class="message-avatar">
            ?
        </div>

        <div class="message-bubble">

            <strong>
                Confirmation required
            </strong>

            <br><br>

            This action will modify your financial data.

            <br><br>

            <button
                class="primary-btn"
                style="
                    padding:7px 12px;
                    font-size:11px;
                "
                onclick="confirmAgentAction('${escapeHtml(action)}', this)">

                Confirm

            </button>

        </div>

    `;


    container.appendChild(
        wrapper
    );


    container.scrollTop =
        container.scrollHeight;

}


/* =========================================================
   CONFIRM AGENT ACTION
   ========================================================= */

async function confirmAgentAction(
    action,
    button
) {

    if (button) {

        button.disabled = true;

        button.textContent =
            "Processing...";

    }


    try {

        const response =
            await fetch(
                "/api/agent",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            message: action,
                            confirm: true
                        })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Action failed."
            );

        }


        addAssistantMessage(
            data.message ||
            "Action completed."
        );


        await loadDashboard();


    } catch (error) {

        console.error(
            error
        );


        addAssistantMessage(
            error.message ||
            "Unable to complete the action."
        );

    }

}


/* =========================================================
   DASHBOARD ERROR
   ========================================================= */

function showDashboardError(message) {

    const resultBox =
        getElement(
            "aiResult"
        );


    const resultText =
        getElement(
            "aiResultText"
        );


    if (resultBox) {

        resultBox.style.display =
            "flex";

    }


    if (resultText) {

        resultText.textContent =
            "Dashboard data could not be loaded: " +
            message;

    }

}


/* =========================================================
   ASSISTANT INPUT
   ========================================================= */

function setupAssistantInput() {

    const input =
        document.getElementById(
            "assistantInput"
        );


    if (!input) {
        return;
    }


    input.addEventListener(
        "keydown",
        function(event) {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                askFinPilot();

            }

        }
    );

}


/* =========================================================
   QUICK QUESTIONS
   ========================================================= */

function setupQuickQuestions() {

    const buttons =
        document.querySelectorAll(
            "[data-question]"
        );


    buttons.forEach(
        button => {

            button.addEventListener(
                "click",
                function() {

                    askQuickQuestion(
                        this.dataset.question
                    );

                }
            );

        }
    );

}


/* =========================================================
   INITIALIZE
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function() {

        setupFilePicker();

        setupAssistantInput();

        setupQuickQuestions();

        loadDashboard();

    }
);


/* =========================================================
   GLOBAL FUNCTIONS
   ========================================================= */

window.loadDashboard =
    loadDashboard;

window.uploadStatement =
    uploadStatement;

window.askFinPilot =
    askFinPilot;

window.askQuickQuestion =
    askQuickQuestion;

window.loadGoalImpact =
    loadGoalImpact;

window.loadBudgetAnalysis =
    loadBudgetAnalysis;

window.confirmAgentAction =
    confirmAgentAction;