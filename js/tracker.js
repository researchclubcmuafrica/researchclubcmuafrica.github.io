// Deadline tracker: loads data/deadlines.json and draws the cards.
// Used by conferences.html, workshops.html, summerschools.html and talks-fellowships.html.
// Each page sets window.TRACKER_CONFIG = { types: [...] } before loading this file, to show only those types.
(function () {
    // ================================================================================
    // "Suggest an opportunity" form. PUT THE GOOGLE FORM LINK HERE (this is the only place).
    // Until it is set, the button says "form coming soon" and does nothing.
    const SUGGEST_FORM_URL = "https://forms.gle/REPLACE-WITH-YOUR-FORM-ID";
    // ================================================================================

    const KIGALI = "Africa/Kigali";
    const AOE = "Etc/GMT+12"; // UTC-12. The sign is reversed in these zone names.
    const DAY = 86400000;

    const kigaliFmt = new Intl.DateTimeFormat("en-GB", {
        timeZone: KIGALI, weekday: "short", day: "numeric", month: "short",
        year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
    });
    const aoeFmt = new Intl.DateTimeFormat("en-GB", {
        timeZone: AOE, day: "numeric", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit", hour12: false,
    });
    const shortFmt = new Intl.DateTimeFormat("en-GB", {
        timeZone: KIGALI, day: "numeric", month: "short", year: "numeric",
    });
    const monthFmt = new Intl.DateTimeFormat("en-GB", {
        timeZone: KIGALI, month: "long", year: "numeric",
    });

    // "Expected around late January 2027", from last edition's deadline.
    function expectedText(conf, now) {
        if (!conf.expectedMs) return null;
        if (conf.expectedMs <= now) return { text: "May have passed: not in our sources yet", cls: "days-passed" };
        const d = new Date(conf.expectedMs);
        const day = Number(new Intl.DateTimeFormat("en-GB", { timeZone: KIGALI, day: "numeric" }).format(d));
        const part = day <= 10 ? "early" : day <= 20 ? "mid" : "late";
        return { text: `Expected around ${part} ${monthFmt.format(d)}`, cls: "days-many" };
    }

    // Icons by field, like the cards on the open conferences page.
    const ICONS = {
        "Machine Learning": "fa-brain",
        "Computer Vision": "fa-eye",
        "Natural Language Processing": "fa-language",
        "Robotics": "fa-robot",
        "Data Mining": "fa-database",
        "Human-Computer Interaction": "fa-hand-pointer",
        "Computer Graphics": "fa-palette",
        "Speech and Signal Processing": "fa-wave-square",
        "Power and Energy Systems": "fa-bolt",
    };

    let conferences = [];
    let showClosed = false;

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function safeLink(url) {
        try {
            const u = new URL(url);
            return (u.protocol === "https:" || u.protocol === "http:") ? u.href : null;
        } catch (e) {
            return null;
        }
    }

    function status(conf, now) {
        if (!conf.deadlineMs) return "tba";
        if (conf.deadlineMs > now) return "open";
        // A yearly event whose deadline has passed goes back to "Upcoming" until a volunteer updates it.
        return conf.recurring ? "tba" : "closed";
    }

    // What to show for an entry that needs a person to check it, or null.
    function checkLabel(conf, now) {
        if (conf.check_date && !conf.deadlineMs) return "Check date";
        if (conf.recurring && conf.deadlineMs && conf.deadlineMs <= now) return "Check next year's date";
        return null;
    }

    function countdownText(ms) {
        if (ms <= 0) return { text: "Deadline passed", cls: "days-passed" };
        const days = Math.floor(ms / DAY);
        const hours = Math.floor((ms % DAY) / 3600000);
        const mins = Math.floor((ms % 3600000) / 60000);
        let text;
        if (days >= 1) text = `${days} day${days === 1 ? "" : "s"}, ${hours} hour${hours === 1 ? "" : "s"} left`;
        else text = `${hours} hour${hours === 1 ? "" : "s"}, ${mins} minute${mins === 1 ? "" : "s"} left`;
        const cls = days < 7 ? "days-urgent" : days <= 30 ? "days-few" : "days-many";
        return { text, cls };
    }

    function detail(icon, text, extraClass) {
        const row = el("div", "detail-item" + (extraClass ? " " + extraClass : ""));
        const i = el("i", "fas " + icon);
        i.setAttribute("aria-hidden", "true");
        row.append(i, el("span", "", text));
        return row;
    }

    function buildCard(conf, now) {
        const st = status(conf, now);
        const card = el("article", "conference-card" + (st === "closed" ? " is-closed" : ""));

        // Header: icon + submission type, deadline, countdown
        const header = el("div", "conference-header");
        const icon = el("div", "conference-icon");
        const iconI = el("i", "fas " + (ICONS[conf.fields[0]] || "fa-file-alt"));
        iconI.setAttribute("aria-hidden", "true");
        icon.append(iconI);

        const meta = el("div", "conference-meta");
        meta.append(el("span", "conference-type", conf.submission_type || "Full paper"));
        if (conf.deadlineMs) {
            const d = new Date(conf.deadlineMs);
            const dl = el("time", "conference-deadline", kigaliFmt.format(d));
            dl.dateTime = conf.deadline_utc;
            meta.append(dl);
            const from = conf.deadline_source === "OpenReview" ? ", from OpenReview" : "";
            if (conf.deadline_timezone === "AoE") {
                meta.append(el("span", "deadline-aoe", `(${aoeFmt.format(d)} AoE${from})`));
            } else if (conf.deadline_timezone) {
                meta.append(el("span", "deadline-aoe", `(organisers' time zone: ${conf.deadline_timezone}${from})`));
            }
            const check = checkLabel(conf, now);
            if (check) {
                meta.append(el("span", "countdown-badge days-few", check));
            } else {
                const cd = countdownText(conf.deadlineMs - now);
                const badge = el("span", "countdown-badge " + cd.cls, cd.text);
                badge.dataset.deadline = conf.deadlineMs;
                meta.append(badge);
            }
        } else {
            meta.append(el("span", "conference-deadline", "Not announced yet"));
            const exp = expectedText(conf, now);
            const check = checkLabel(conf, now);
            meta.append(el("span", "countdown-badge " + (exp && !check ? exp.cls : "days-few"),
                check || (exp ? exp.text : "Check the official page")));
        }
        header.append(icon, meta);

        // Body
        const body = el("div", "conference-content");
        const pills = el("div", "status-row");
        if (st === "open") pills.append(el("span", "pill pill-open", "Open"));
        if (st === "closed") pills.append(el("span", "pill pill-closed", "Closed"));
        if (st === "tba") pills.append(el("span", "pill pill-tba", checkLabel(conf, now) || "Upcoming"));
        // Type badge only on a page that mixes types (on the Workshops page every card is a workshop).
        if (!SINGLE_TYPE && conf.type && conf.type !== "Conference") pills.append(el("span", "pill pill-type", conf.type));
        if (conf.africa) pills.append(el("span", "pill pill-africa", "African venue"));
        body.append(pills);

        body.append(el("h3", "conference-title", conf.name));
        if (conf.full_name) body.append(el("p", "conference-fullname", conf.full_name));
        body.append(el("p", "conference-theme", conf.fields.join(", ")));

        const details = el("div", "conference-details");
        if (conf.parent) details.append(detail("fa-sitemap", `${conf.type || "Workshop"} at ${conf.parent}`));
        details.append(detail("fa-calendar-alt", conf.event_dates || "To be announced", "date-item"));
        details.append(detail("fa-map-marker-alt", conf.location || "To be announced"));
        if (conf.abstractMs) {
            const passed = conf.abstractMs <= now ? " (passed)" : "";
            details.append(detail("fa-file-signature",
                `Abstract due ${kigaliFmt.format(new Date(conf.abstractMs))} Kigali time${passed}`));
        }
        if (conf.note) details.append(detail("fa-info-circle", conf.note));
        if (conf.last_deadline_utc) {
            details.append(detail("fa-history",
                `Last deadline (${conf.last_edition}): ${shortFmt.format(new Date(conf.last_deadline_utc))}`));
        }
        // OpenReview date, unless it is the same as the deadline or abstract date already shown.
        const sameAs = ms => ms && Math.abs(conf.openreviewMs - ms) <= 3600000;
        if (conf.openreviewMs && !sameAs(conf.deadlineMs) && !sameAs(conf.abstractMs)) {
            const passed = conf.openreviewMs <= now ? " (passed)" : "";
            details.append(detail("fa-file-upload",
                `OpenReview submission form closes ${kigaliFmt.format(new Date(conf.openreviewMs))} Kigali time${passed}`));
        }
        const orHref = safeLink(conf.openreview_link);
        if (orHref) {
            const row = el("div", "detail-item");
            const oi = el("i", "fas fa-check-circle");
            oi.setAttribute("aria-hidden", "true");
            const a = el("a", "", "Submission page on OpenReview");
            a.href = orHref;
            a.target = "_blank";
            a.rel = "noopener";
            row.append(oi, a);
            details.append(row);
        }
        body.append(details);

        const href = safeLink(conf.link);
        if (href) {
            const a = el("a", "conference-link");
            a.href = href;
            a.target = "_blank";
            a.rel = "noopener";
            const ai = el("i", "fas fa-external-link-alt");
            ai.setAttribute("aria-hidden", "true");
            const lastSite = conf.upcoming && !conf.openreview_link;
            const apply = conf.type === "Summer school" || conf.type === "Fellowship";
            a.append(ai, document.createTextNode(
                lastSite ? "Last edition's website" : apply ? "View and Apply" : "View Details"));
            a.setAttribute("aria-label", `View details for ${conf.name} (opens in a new tab)`);
            body.append(a);
        }

        card.append(header, body);
        return card;
    }

    function render() {
        const now = Date.now();
        const field = document.getElementById("fieldFilter").value;
        const type = document.getElementById("typeFilter").value;
        const searchBox = document.getElementById("searchInput");
        const words = (searchBox ? searchBox.value : "").toLowerCase().split(/\s+/).filter(Boolean);
        const list = conferences.filter(c =>
            (field === "all" || c.fields.includes(field)) && (type === "all" || c.type === type) &&
            words.every(w => c.searchText.includes(w)));

        const open = list.filter(c => status(c, now) === "open").sort((a, b) => a.deadlineMs - b.deadlineMs);
        // Upcoming: soonest expected first, then ones whose expected date has passed, then no guess at all.
        const rank = c => !c.expectedMs ? 2 : c.expectedMs <= now ? 1 : 0;
        const tba = list.filter(c => status(c, now) === "tba").sort((a, b) =>
            rank(a) - rank(b) || (a.expectedMs || 0) - (b.expectedMs || 0) || a.name.localeCompare(b.name));
        // Closed last, most recently closed first.
        const closed = list.filter(c => status(c, now) === "closed").sort((a, b) => b.deadlineMs - a.deadlineMs);

        const fill = (id, items) => {
            const grid = document.getElementById(id);
            grid.replaceChildren(...items.map(c => buildCard(c, now)));
        };
        fill("openGrid", open);
        fill("tbaGrid", tba);
        fill("closedGrid", closed);

        document.getElementById("openCount").textContent = open.length;
        document.getElementById("tbaCount").textContent = tba.length;
        document.getElementById("closedCount").textContent = closed.length;
        const empty = document.getElementById("openEmpty");
        const filtered = words.length > 0 || field !== "all" || type !== "all";
        empty.textContent = !filtered ? "No open deadlines right now."
            : list.length === 0 ? "Nothing matches your search. Try fewer words or another field."
                : tba.length > 0 ? "No open deadlines match your search. See the upcoming ones below."
                    : "Only closed deadlines match your search. Use \"Show closed deadlines\" below to see them.";
        empty.classList.toggle("hidden", open.length > 0);
        document.getElementById("tbaGroup").classList.toggle("hidden", tba.length === 0);
        document.getElementById("closedGroup").classList.toggle("hidden", closed.length === 0);
        document.getElementById("closedGrid").classList.toggle("hidden", !showClosed);

        const soon = open.filter(c => c.deadlineMs - now <= 30 * DAY).length;
        const what = type === "all" ? "" : ` (${TYPE_PLURALS[type] || type})`;
        const label = (field === "all" ? "" : ` in ${field}`) + what;
        document.getElementById("statOpen").textContent = `${open.length} open deadline${open.length === 1 ? "" : "s"}${label}`;
        document.getElementById("statSoon").textContent = `${soon} closing in the next 30 days`;
        document.getElementById("statUpcoming").textContent = `${tba.length} upcoming`;
    }

    // Update the countdowns every 30 seconds. Redraw the lists if a deadline has just passed.
    function tick() {
        const now = Date.now();
        let changed = false;
        document.querySelectorAll(".countdown-badge[data-deadline]").forEach(badge => {
            const ms = Number(badge.dataset.deadline) - now;
            const cd = countdownText(ms);
            if (ms <= 0 && !badge.classList.contains("days-passed")) changed = true;
            badge.textContent = cd.text;
            badge.className = "countdown-badge " + cd.cls;
        });
        if (changed) render();
    }

    // Which types this page shows (null = all). Set by the page in window.TRACKER_CONFIG.
    const ALLOWED_TYPES = (window.TRACKER_CONFIG && window.TRACKER_CONFIG.types) || null;
    const SINGLE_TYPE = !!ALLOWED_TYPES && ALLOWED_TYPES.length === 1;

    // Kinds of opportunity, in the same order as the data script.
    const TYPES = ["Conference", "Workshop", "Summer school", "Community talk", "Fellowship"];
    const TYPE_PLURALS = {
        "Conference": "conferences", "Workshop": "workshops", "Summer school": "summer schools",
        "Community talk": "community talks", "Fellowship": "fellowships",
    };

    function fillTypeFilter() {
        // Only one type on this page: no need for a Type filter.
        if (ALLOWED_TYPES && ALLOWED_TYPES.length === 1) {
            const select = document.getElementById("typeFilter");
            const group = select.closest(".filter-group");
            if (group) group.hidden = true;
            select.hidden = true;
            document.querySelector('label[for="typeFilter"]').hidden = true;
            return;
        }
        const counts = new Map();
        conferences.forEach(c => counts.set(c.type, (counts.get(c.type) || 0) + 1));
        const select = document.getElementById("typeFilter");
        TYPES.filter(t => counts.get(t)).forEach(t => {
            const opt = el("option", "", `${t} (${counts.get(t)})`);
            opt.value = t;
            select.append(opt);
        });
    }

    function fillFieldFilter() {
        const counts = new Map();
        conferences.forEach(c => c.fields.forEach(f => counts.set(f, (counts.get(f) || 0) + 1)));
        const select = document.getElementById("fieldFilter");
        [...counts.keys()].sort().forEach(f => {
            const opt = el("option", "", `${f} (${counts.get(f)})`);
            opt.value = f;
            select.append(opt);
        });
    }

    async function loadPartials() {
        try {
            const [navRes, footerRes] = await Promise.all([fetch("navigation.html"), fetch("footer.html")]);
            if (navRes.ok) {
                document.getElementById("navigation-container").innerHTML = await navRes.text();
                if (window.initializeNavigation) window.initializeNavigation();
            }
            if (footerRes.ok) {
                document.getElementById("footer-container").innerHTML = await footerRes.text();
            }
        } catch (e) {
            console.error("Error loading navigation or footer:", e);
        }
    }

    async function loadDeadlines() {
        try {
            const res = await fetch("data/deadlines.json", { cache: "no-cache" });
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();
            conferences = (data.conferences || []).map(c => ({
                ...c,
                fields: Array.isArray(c.fields) && c.fields.length ? c.fields : ["Other"],
                type: c.type || "Conference",
                deadlineMs: c.deadline_utc ? Date.parse(c.deadline_utc) : null,
                abstractMs: c.abstract_deadline_utc ? Date.parse(c.abstract_deadline_utc) : null,
                openreviewMs: c.openreview_deadline_utc ? Date.parse(c.openreview_deadline_utc) : null,
                expectedMs: c.expected_deadline_utc ? Date.parse(c.expected_deadline_utc) : null,
            })).filter(c => !ALLOWED_TYPES || ALLOWED_TYPES.includes(c.type));
            // Text the search box looks in: name, full name, fields, place, main conference, note.
            conferences.forEach(c => {
                c.searchText = [c.name, c.full_name, c.fields.join(" "), c.location, c.parent, c.note, c.type]
                    .filter(Boolean).join(" ").toLowerCase();
            });
            fillTypeFilter();
            fillFieldFilter();
            render();
            setInterval(tick, 30000);

            const src = document.getElementById("dataSource");
            const sources = Array.isArray(data.sources) ? data.sources : (data.source ? [data.source] : []);
            src.append("Deadlines come from ");
            sources.forEach((s, i) => {
                const a = el("a", "", s.label);
                a.href = safeLink(s.url) || "#";
                a.target = "_blank";
                a.rel = "noopener";
                const sep = i === 0 ? "" : i === sources.length - 1 ? " and " : ", ";
                src.append(sep, a);
            });
            src.append(", plus African venues added by the Research Club. ");
            const notices = el("a", "", "Data credits and licences");
            notices.href = "data/THIRD_PARTY_NOTICES.md";
            notices.target = "_blank";
            notices.rel = "noopener";
            src.append(notices, ".");
            if (data.updated_at) {
                const updated = new Date(data.updated_at);
                const t = document.getElementById("lastUpdatedTime");
                t.dateTime = data.updated_at;
                t.textContent = kigaliFmt.format(updated);
                document.getElementById("lastUpdated").hidden = false;
                src.append(` Last updated on ${shortFmt.format(updated)}.`);
            }
        } catch (e) {
            console.error("Error loading deadlines:", e);
            document.getElementById("statOpen").textContent = "List not available";
            document.getElementById("loadError").classList.remove("hidden");
        }
    }

    function setUpSuggestLink() {
        const link = document.getElementById("suggestLink");
        if (!link) return;
        if (SUGGEST_FORM_URL.includes("REPLACE-WITH")) {
            link.removeAttribute("href");
            link.removeAttribute("target");
            link.setAttribute("aria-disabled", "true");
            link.classList.add("is-disabled");
            link.append(" (form coming soon)");
        } else {
            link.href = SUGGEST_FORM_URL;
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        setUpSuggestLink();
        document.getElementById("fieldFilter").addEventListener("change", render);
        document.getElementById("typeFilter").addEventListener("change", render);
        const searchBox = document.getElementById("searchInput");
        if (searchBox) searchBox.addEventListener("input", render);
        document.getElementById("toggleClosed").addEventListener("click", function () {
            showClosed = !showClosed;
            this.setAttribute("aria-expanded", String(showClosed));
            this.innerHTML = showClosed
                ? '<i class="fas fa-eye-slash" aria-hidden="true"></i> Hide closed deadlines'
                : '<i class="fas fa-eye" aria-hidden="true"></i> Show closed deadlines';
            document.getElementById("closedGrid").classList.toggle("hidden", !showClosed);
        });
        loadPartials();
        loadDeadlines();
    });
})();
