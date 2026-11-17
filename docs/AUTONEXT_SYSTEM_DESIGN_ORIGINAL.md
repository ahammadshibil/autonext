# AutoNext: Terminal-Native Deeptech Company Intelligence

Status: proposed system design  
First vertical: photonics  
Primary user: a technically literate investor/analyst running a proprietary company-building and investment thesis across public and private companies

## 1. Product decision

AutoNext should be a thin orchestration and judgment layer over the systems that already exist:

- **Deeptech Scout** discovers companies, people, papers, patents, funding, and market signals.
- **Deeptech Radar** supplies sector context, frontier maps, and an initial company universe.
- **Assay** verifies founder provenance, IP ownership, grants, scientific claims, and independent replication.
- **Conviction** stores theses, runs bull/bear and counter-thesis reviews, and records how conviction changes.
- **AutoNext** resolves identities, creates a point-in-time evidence ledger, runs a thesis against a comparable universe, computes transparent rankings, and explains every conclusion.

AutoNext is therefore not a fifth research engine. It is the system that makes the other four composable, reproducible, and useful at portfolio scale.

The recommended implementation is a new Python repository named `autonext`. It should use Scout and Conviction through stable HTTP/JSON interfaces and use Assay through its Python API or JSON CLI. It should not import the internal database models of the TypeScript applications.

## 2. What success looks like

A user can define a photonics thesis once and then run:

```console
autonext universe build photonics --public --private --as-of 2026-11-15
autonext run photonics --as-of 2026-11-15
autonext rank photonics --cohort public
autonext company show lightmatter
autonext explain lightmatter
autonext compare lightmatter ayar-labs celestial-ai
autonext export photonics --format memo
```

The result is not merely a spreadsheet of scores. It is a reproducible research object containing:

- the universe definition and exclusions;
- company and security identity resolution;
- every material claim and the evidence supporting or contradicting it;
- the date at which each fact was knowable;
- technical, commercial, financial, timing, and fragility assessments;
- the ranking formula and weights used;
- evidence coverage and confidence;
- an adversarial counter-thesis;
- the next fact or event most likely to change the conclusion;
- a diff from the previous run.

## 3. Non-goals

The first version should not:

- execute trades;
- pretend private and public companies are directly comparable;
- use an opaque language-model score as the source of truth;
- replace sector-specific technical diligence with a universal questionnaire;
- create a live web application before the terminal workflow is reliable;
- autonomously publish conclusions or contact companies;
- rewrite Scout, Assay, Radar, or Conviction.

## 4. Core design principles

### 4.1 Evidence first, score second

Every score must be derived from claims and observations that link to sources. A conclusion without a source, observation date, and confidence is a note, not evidence.

### 4.2 Point-in-time integrity

Every run requires an `as_of` date. The system must never use a filing, paper, price, funding announcement, or customer event published after that date when reproducing an older run.

### 4.3 Unknown is not zero

Missing information is represented as unknown. The output displays both quality and coverage. A company with weak evidence cannot outrank a well-evidenced company merely because its unknowns were interpreted optimistically.

### 4.4 Deterministic core, probabilistic synthesis

Identity resolution, date filters, financial calculations, evidence coverage, gates, and ranking are deterministic. Language models may extract claims, summarize evidence, generate counter-theses, and explain rankings, but cannot silently change raw observations or weights.

### 4.5 Human judgment is visible

Analyst overrides are allowed, but stored separately with author, time, reason, previous value, and expiry/review date. The system must make a machine conclusion distinguishable from an analyst judgment.

### 4.6 Vertical depth behind a common contract

Photonics, biotechnology, semiconductors, space, batteries, and quantum systems share a common evidence model but not identical technical metrics. Each vertical implements its own technical module behind a stable interface.

## 5. High-level architecture

```text
                         thesis.yaml
                              |
                              v
  Radar / Scout ----> Universe Builder ----> Entity Resolver
  filings / APIs ----> Source Adapters  ----> Canonical Company Graph
  papers / patents --> Source Adapters  ----> Evidence Ledger
                              |                       |
                              v                       v
                    Deterministic Metrics      Claim Verification
                    financial / market         Assay / vertical checks
                              |                       |
                              +-----------+-----------+
                                          v
                                  Causal Market Model
                                  architecture / actors
                                  constraints / expectations
                                          |
                                          v
                                  Gates + Pillar Scores
                                          |
                                          v
                              Multi-agent Investment Committee
                                          |
                                          v
                      Rank / Explain / Compare / Export / Diff
```

### Components

1. **CLI** — command surface, validation, progress, tables, and exports.
2. **Run engine** — a resumable, idempotent directed workflow.
3. **Universe builder** — converts a sector definition into candidates and records inclusion/exclusion reasons.
4. **Entity resolver** — creates canonical company, person, subsidiary, and security identities.
5. **Source adapters** — collect source documents and structured observations.
6. **Evidence ledger** — immutable source snapshots, hashes, publication dates, observation dates, and provenance.
7. **Analyzers** — deterministic financial calculations, Assay checks, and vertical-specific technical analysis.
8. **Causal market model** — actors, incentives, architecture changes, migrating constraints, value capture, feedback loops, expectations, and scenario propagation.
9. **Thesis engine** — gates, pillar scores, weights, confidence, and ranking profiles.
10. **Investment committee** — a structured multi-agent deliberation with blind analysis, bull/bear cases, cross-examination, counter-thesis, and preserved dissent.
11. **Report layer** — terminal views plus JSON, CSV, Markdown, and later HTML.

## 6. Repository boundaries

```text
autonext/
  pyproject.toml
  src/autonext/
    cli/
    core/
      models.py
      runs.py
      evidence.py
      identity.py
      scoring.py
    adapters/
      scout.py
      radar.py
      assay.py
      conviction.py
      filings.py
      market_data.py
      papers.py
      patents.py
    verticals/
      base.py
      photonics/
        taxonomy.yaml
        metrics.py
        analyzers.py
        thesis.yaml
    storage/
      sqlite.py
      parquet.py
    reports/
      terminal.py
      markdown.py
      json_export.py
  tests/
    fixtures/
    unit/
    integration/
```

Integration rule: AutoNext owns orchestration, canonical identities, evidence, run state, and ranking. Existing repositories remain the owners of their specialized capabilities.

## 7. Provider contracts

Every integration should implement a small typed contract rather than leaking vendor-specific data into the core.

```python
class DiscoveryProvider(Protocol):
    async def discover(self, query: UniverseQuery) -> list[Candidate]: ...

class EvidenceProvider(Protocol):
    async def collect(self, entity: EntityRef, as_of: date) -> list[EvidenceItem]: ...

class Analyzer(Protocol):
    async def analyze(
        self,
        entity: EntityRef,
        evidence: list[EvidenceItem],
        thesis: ThesisDefinition,
    ) -> list[Finding]: ...
```

The normalized output contract should include:

- `provider`
- `provider_record_id`
- `retrieved_at`
- `published_at`
- `valid_from` and `valid_to`, when applicable
- `as_of_eligible`
- `source_url`
- `content_hash`
- `raw_snapshot_ref`
- `license_or_usage_note`
- `extraction_method`
- `confidence`

## 8. Canonical data model

### Identity

- `Company`
- `CompanyAlias`
- `SubsidiaryRelationship`
- `Person`
- `PersonCompanyRole`
- `Security`
- `ExchangeListing`
- `ExternalIdentifier`
- `EntityResolutionDecision`

### Research evidence

- `SourceDocument`
- `EvidenceItem`
- `Claim`
- `ClaimEvidenceLink`
- `Contradiction`
- `Verification`
- `MetricDefinition`
- `MetricObservation`
- `Patent`
- `Paper`
- `Grant`
- `FundingEvent`
- `CommercialReceipt`
- `Catalyst`
- `MarketActor`
- `ActorIncentive`
- `ValueChainNode`
- `ArchitectureState`
- `Constraint`
- `CausalEdge`
- `FeedbackLoop`
- `ProfitPool`
- `ExpectationSnapshot`
- `Scenario`
- `ScenarioConsequence`
- `FounderProfile`
- `FounderBelief`
- `StrategicDecision`
- `StrategicCommitment`
- `FounderPrediction`
- `EmployeeSignal`
- `CultureTheme`
- `TalentFlow`
- `OrganizationalCapability`
- `NarrativeBehaviorGap`

### Thesis and decisions

- `UniverseDefinition`
- `UniverseMembership`
- `ThesisDefinition`
- `ThesisVersion`
- `AnalysisRun`
- `Finding`
- `GateResult`
- `PillarScore`
- `RankSnapshot`
- `CounterThesis`
- `AnalystOverride`
- `DecisionLog`

### Required temporal fields

Every material record carries some combination of:

- `published_at`: when a source became public;
- `observed_at`: when AutoNext first collected it;
- `effective_at`: when the underlying event took effect;
- `as_of`: the boundary of the analysis run;
- `superseded_at`: when a later record replaced it.

This is essential for backtesting the thesis without look-ahead bias.

## 9. Thesis definition

The book's ideas should become explicit research fields, not prose hidden inside prompts.

```yaml
id: photonics-v1
name: Photonics company architecture
version: 1

cohorts:
  - public
  - private

gates:
  identity_confidence_min: 0.85
  evidence_coverage_min: 0.50
  exclude_if:
    - fatal_ip_ownership_issue
    - insolvent_before_next_catalyst
    - core_claim_disproved

pillars:
  technical_truth:
    weight: 0.18
  thesis_fit:
    weight: 0.14
  product_and_acceptance:
    weight: 0.16
  market_and_distribution:
    weight: 0.12
  complementary_assets:
    weight: 0.10
  financial_quality_or_runway:
    weight: 0.12
  catalyst_and_timing:
    weight: 0.10
  team_ip_and_provenance:
    weight: 0.08

penalties:
  fragility: 0.15
  customer_concentration: 0.05
  financing_dependency: 0.10
```

The thesis module should encode the user's recurring ideas:

- Nature Frontier versus Market Frontier;
- whether the company is a David, arms a David, or supplies the incumbent architecture;
- Research -> Technology -> Product -> Distribution;
- whether the layers reinforce one another;
- the Difficult Middle and Acceptance Ladder;
- complementary assets and distribution control;
- capital path and financing mismatch;
- the death variable;
- receipts rather than announcements;
- discovery, recognition, and monetization clocks;
- the next forcing catalyst.

## 10. Ranking design

There should not be a single unexplained master score.

### 10.1 Separate cohorts

Public and private companies are ranked separately by default. Public securities can include valuation, price, liquidity, and dated catalysts. Private companies can include financing runway, round structure, and probability of reaching the next acceptance milestone. A mixed list may be produced as a strategic watchlist, not an investment ranking.

### 10.2 Pillar score

Each pillar has:

- a score from 0 to 5;
- confidence from 0 to 1;
- evidence coverage from 0 to 1;
- source-quality distribution;
- contradictions and unresolved questions;
- the observations that produced the score.

For pillars with sufficient evidence:

```text
base_quality = sum(weight_i * score_i) / sum(weight_i present)
coverage     = sum(weight_i present) / sum(all weights)
```

Missing pillars are not scored as zero. Instead, the rank view displays both `base_quality` and `coverage`, and applies an explicit configurable uncertainty haircut when a single ordering is required:

```text
evidence_adjusted_quality = base_quality * (0.60 + 0.40 * coverage)
```

The coefficient is a policy choice, stored in the thesis version, not a hidden constant.

### 10.3 Outputs

AutoNext should expose at least four useful orderings:

1. **Quality rank** — the company architecture and current execution.
2. **Evidence rank** — quality adjusted for coverage and source confidence.
3. **Timing rank** — probability-weighted value around the next forcing catalyst for public securities.
4. **Research priority** — expected decision value of resolving the next unknown.

The research-priority rank is important. It directs analyst time toward facts most likely to change the decision rather than merely producing more information.

### 10.4 Explainability

`autonext explain COMPANY` must answer:

- Why is this company ranked here?
- Which three observations contributed most?
- Which penalties hurt it most?
- What is unknown?
- What evidence contradicts the thesis?
- What single new fact would most change the rank?
- What changed since the last run?

## 10.5 Multi-agent investment committee

AutoNext should use multiple agents, but the agents should represent different **responsibilities, priors, and failure sensitivities**, not merely different writing styles. The useful disagreement is epistemic: each agent should notice a different way the investment can work or fail.

The user's existing repositories already contain two valuable precedents:

- `wealth-agent` runs Buffett, Munger, Burry, Ackman, and India-context personas in parallel and then synthesizes the votes.
- `lab-signal` improves the pattern with typed tool outputs, domain-selected personas, literature grounding, separate bull and bear researchers, a generated counter-thesis, and a full panel that evaluates the counter-thesis.

AutoNext should reuse the second pattern and harden it for evidence-based ranking.

### Committee roles

The default committee should be functional rather than celebrity-based:

1. **Technical truth analyst** — mechanism, benchmark quality, replication, and scientific uncertainty.
2. **Scale and manufacturing analyst** — yield, packaging, reliability, supply chain, capex, and qualification.
3. **Product and acceptance analyst** — user workflow, switching burden, design wins, paid pilots, and receipts.
4. **Market and distribution analyst** — market structure, buyer power, route to market, complements, and incumbent response.
5. **Financial forensic analyst** — revenue quality, margins, cash conversion, dilution, runway, and accounting risks.
6. **Catalyst and timing analyst** — discovery, recognition, and monetization clocks; dated forcing events.
7. **Architecture analyst** — thesis fit, company position in the value chain, reinforcement across research/technology/product/distribution, and Goliath response.
8. **Red-team analyst** — strongest coherent failure case, hidden dependency, death variable, and disconfirming evidence.
9. **Evidence auditor** — source quality, identity, time leakage, unsupported assertions, and unresolved contradictions.

Sector modules can add specialist seats. Photonics may add a fabrication/packaging expert; biotechnology may add clinical, regulatory, and CMC experts.

### Deliberation protocol

```text
Canonical point-in-time evidence packet
                  |
                  v
       Round 1: blind independent memos
                  |
                  v
      Bull case + bear case + counter-thesis
                  |
                  v
      Round 2: claim-level cross-examination
                  |
                  v
       Round 3: revised scores and beliefs
                  |
                  v
       Adjudicator + minority report
                  |
                  v
        Deterministic ranking engine
```

#### Round 1 — blind analysis

Each agent receives the same canonical evidence packet but does not see other agents' opinions. This reduces anchoring and false unanimity. Every output is structured:

```json
{
  "role": "technical_truth",
  "pillar_scores": {"technical_truth": 4.1},
  "confidence": 0.72,
  "supporting_claim_ids": ["claim-14", "claim-27"],
  "contradicting_claim_ids": ["claim-31"],
  "key_risk": "Packaging loss may erase the die-level advantage",
  "falsifier": "Independent packaged-module benchmark below target",
  "next_questions": ["...", "...", "..."]
}
```

An agent cannot contribute a score without linking it to claim IDs. Unsupported statements are retained as hypotheses, not evidence.

#### Round 2 — cross-examination

Agents do not conduct an unbounded chat. Each may challenge a limited number of material claims or assumptions:

- identify the exact claim ID;
- state the objection;
- request the evidence or calculation needed to resolve it;
- nominate whether the challenge affects a gate, pillar score, confidence, or catalyst.

This creates an auditable dispute graph instead of a long conversational transcript.

#### Round 3 — belief revision

After seeing challenges and responses, every affected agent submits:

- revised score and confidence;
- previous score;
- reason for the change or refusal to change;
- evidence responsible for the update.

The system should reward correct updating, not rhetorical consistency.

#### Adjudication

The adjudicator produces:

- strongest supported bull case;
- strongest supported bear case;
- resolved disagreements;
- unresolved disagreements;
- committee consensus;
- minority report;
- next disconfirming event;
- whether the company is rankable with current evidence.

The minority report is never discarded. Disagreement is often the most valuable result, particularly when technical quality, commercial timing, and valuation point in different directions.

### How committee output affects ranking

The committee should not determine rank by majority vote. Five agents using the same model can repeat the same error five times.

Instead:

- deterministic observations and calculations remain the base layer;
- each role may score only its assigned pillars;
- the evidence auditor can reduce confidence or block point-in-time-invalid evidence;
- agent scores are reliability-weighted using performance on golden cases;
- the red team can trigger gates or penalties only when its case links to evidence;
- the adjudicator explains the outcome but cannot silently change weights;
- the ranking engine applies the versioned thesis formula after deliberation.

For top candidates, AutoNext should also run pairwise comparisons. Asking “Which of these two better satisfies this pillar, and why?” is often more stable than asking for absolute 1–10 scores across hundreds of companies.

### Calibration and anti-groupthink controls

- Use blind first-round analysis.
- Randomize company order and remove brand/ticker names in selected calibration runs.
- Use more than one model family for high-value or disputed cases when budget permits.
- Track each role's confidence calibration, unsupported-claim rate, and historical error by pillar.
- Do not reward agreement itself; reward evidence-linked accuracy and useful dissent.
- Reject invented citations and sources published after the run's `as_of` date.
- Preserve prompts, model/version, structured outputs, and revisions in the run manifest.
- Re-run only agents whose input evidence changed, unless a full committee refresh is requested.

### Cost-aware execution

Run the committee in layers:

1. deterministic screening across the entire universe;
2. smaller inexpensive panels for companies clearing the gates;
3. full cross-examining committee for the top candidates and ambiguous cases;
4. stronger-model adjudication for decisions with meaningful capital or research consequences.

This makes multi-agent reasoning a scarce diligence resource rather than an expensive theatrical layer applied equally to every company.

## 10.6 Causal market intelligence and third-order effects

Company analysis alone is insufficient. AutoNext must understand how a technical state change propagates through an industry and how private and public markets interpret that change at different speeds.

The missing layer is a **causal market model** between the evidence ledger and the investment committee. Its purpose is not to predict everything. Its purpose is to make the chain of reasoning explicit, falsifiable, and comparable.

### The four levels of reasoning

For every important technological or market change, the system asks:

1. **State change — what became newly possible or impossible?**  
   A scientific bottleneck is removed, a cost curve crosses a threshold, qualification is achieved, regulation changes, or a production method reaches acceptable yield.

2. **First-order effect — who experiences the direct consequence?**  
   Direct demand rises or falls, a product becomes feasible, a customer saves cost, or an existing product becomes obsolete.

3. **Second-order effect — how do other actors respond?**  
   Incumbents acquire or bundle, customers dual-source, suppliers add capacity, standards emerge, regulators intervene, capital floods the category, or a complementary bottleneck becomes binding.

4. **Third-order effect — what new equilibrium forms?**  
   Profit pools migrate, bargaining power changes, some components commoditize, new toll collectors emerge, capital intensity moves, industry boundaries change, and public-market expectations eventually reset.

This is the distinction between noticing that a technology is important and understanding who will capture its economics.

### Causal edge contract

Every proposed effect is stored as an edge, not buried inside prose:

```json
{
  "from": "electrical_io_scaling_limit",
  "to": "optical_interconnect_adoption",
  "relation": "accelerates",
  "order": 1,
  "actor": "hyperscale_customer",
  "mechanism": "bandwidth and power constraints",
  "conditions": ["cost_per_bit_threshold_met", "packaging_qualified"],
  "lag_months": {"low": 12, "base": 24, "high": 48},
  "magnitude": "material",
  "confidence": 0.68,
  "supporting_claim_ids": ["claim-104", "claim-118"],
  "disconfirming_claim_ids": ["claim-123"],
  "falsifier": "electrical architecture extends without economic penalty"
}
```

An agent may propose a causal edge, but the evidence auditor validates its sources and dates. The committee debates disputed edges. The scenario engine propagates only accepted or explicitly uncertain edges.

### Market graph

The graph should contain more than companies:

```text
technology capability
    -> product architecture
    -> customer workflow and procurement
    -> complementary bottleneck
    -> supplier capacity and capital spending
    -> standards and regulation
    -> incumbent strategic response
    -> profit-pool and bargaining-power change
    -> company financial materiality
    -> consensus expectation revision
    -> security price recognition
```

Node types include technologies, technical constraints, products, customers, suppliers, complements, regulators, standards bodies, capital providers, profit pools, private companies, public companies, and securities.

### Actor and incentive model

Third-order effects usually arise because actors respond rather than remain static. Each important actor therefore needs:

- objective or payoff;
- current advantage;
- constraint;
- likely action set;
- ability to delay or block adoption;
- switching cost;
- time horizon;
- evidence of prior behavior in similar transitions.

For example, an incumbent may rationally slow a technically superior architecture if it cannibalizes a profitable installed base. A hyperscaler may accelerate adoption but vertically integrate the most valuable layer. A supplier may overbuild capacity after observing the same demand signal as every competitor. These responses can reverse a simple first-order thesis.

### Architecture-transition record

The architecture analysis already developed in `lagging-signal` should become a first-class AutoNext object:

```yaml
old_architecture: How the industry works today
uncertainty_removed: What technical or economic question changed
new_architecture: What can now be built or purchased differently
next_constraint: What becomes scarce if adoption proceeds
incumbent_responses:
  - acquire
  - build
  - bundle
  - litigate
  - standardize
  - defend
  - retreat
profit_pool_migration:
  winners: []
  losers: []
  toll_collectors: []
disconfirmation: What would show the transition is not occurring
```

### Scenario engine

AutoNext should generate a small number of coherent worlds rather than independent optimistic and pessimistic line items:

- **Continuation:** the present architecture improves enough to remain dominant.
- **Transition:** the new architecture reaches adoption on the expected path.
- **Acceleration:** a reinforcing loop compresses adoption time.
- **Bottleneck shift:** the technology works, but value migrates to a complement or constraint.
- **Capital-cycle reversal:** enthusiasm causes overcapacity, price compression, or destructive financing.
- **Incumbent capture:** incumbents absorb the innovation and private challengers create little standalone value.

Every scenario specifies trigger conditions, causal edges, probability range, time path, company-level consequences, expectation changes, and observables that distinguish it from competing scenarios.

The system must avoid multiplying uncertain edge probabilities as if they were independent. Shared assumptions and correlated failure modes are recorded explicitly.

### Illustrative photonics chain

The following is a hypothesis template, not a pre-accepted conclusion:

```text
Larger AI clusters expose electrical interconnect power/bandwidth limits
    -> demand for optical interconnect rises                         [first order]
    -> packaging, lasers, testing, yield, and thermal integration
       become the binding constraints                               [second order]
    -> hyperscalers dual-source or vertically integrate; incumbents
       acquire capabilities; standards reduce switching friction    [second order]
    -> some optical modules commoditize while scarce packaging,
       test, process IP, or installed distribution captures value   [third order]
    -> industry capacity additions may later create oversupply,
       shifting returns away from the initial headline winners      [third order]
```

AutoNext's job is to identify which arrows are supported, which remain speculative, when they should become observable, and which companies have material economic exposure to each outcome.

### Separate investment lenses

A great technology, a great company, a great venture investment, and a great public security are four different conclusions.

#### Deeptech venture lens

Evaluate:

- technical probability and milestone tree;
- founder learning velocity and unique access;
- IP and freedom to operate;
- capital required to reach the next acceptance milestone;
- follow-on financing and dilution risk;
- wedge, market creation, and possible power-law outcome;
- exit paths and likely strategic acquirers;
- ownership available relative to risk.

#### Deeptech public-market lens

Evaluate:

- economic materiality to the listed company;
- what current price and consensus already imply;
- management's willingness and ability to capture the shift;
- cannibalization and capital-allocation burden;
- balance-sheet survival until recognition;
- liquidity and position-size constraints;
- forcing catalyst and time to recognition;
- success and failure values relative to today's price.

#### Bridge lens

Evaluate how private activity changes the public opportunity set:

- Is specialist capital resolving technical uncertainty or merely following a public narrative?
- Is the meaningful unit one startup or a funded architecture cohort?
- Which new constraint becomes important across the cohort?
- Which listed company has material and defensible exposure?
- Is that exposure absent from point-in-time expectations?
- What dated event forces recognition?

### Four distinct rankings

AutoNext should never collapse all decisions into one universal league table. It should produce:

1. **Technology rank** — which technical approaches are most credible.
2. **Company-quality rank** — which organizations are best positioned to execute and capture value.
3. **Venture-investment rank** — which private opportunities offer the best ownership-adjusted power-law return.
4. **Public-security rank** — which listed exposures offer the best probability × payoff × recognition-time asymmetry relative to price.

A fifth queue, **research priority**, ranks unresolved questions by expected decision value.

### Market-intelligence agents

The company committee can dynamically summon market-level specialists:

- technology diffusion historian;
- value-chain and bottleneck mapper;
- customer procurement analyst;
- incumbent strategy and game-theory analyst;
- capital-cycle and capacity analyst;
- standards/regulatory/geopolitical analyst;
- public expectations and consensus analyst;
- cross-domain second- and third-order scout.

These agents do not write free-form essays first. They propose or challenge actors, constraints, causal edges, lags, and scenario consequences. Narrative is generated after the graph is coherent.

### Terminal commands

```console
autonext market map photonics --as-of 2026-11-16
autonext architecture show photonics
autonext causal trace electrical-io-limit --orders 3
autonext scenario run photonics --scenario transition
autonext scenario compare photonics
autonext expectations gap COMPANY_ID
autonext rank photonics --lens venture
autonext rank photonics --lens public
autonext trace COMPANY_ID --to recognition
```

The most valuable command may be:

```console
autonext ask photonics "If this succeeds, what becomes scarce next?"
```

That question repeatedly converts a visible first-order theme into a less obvious, potentially more valuable research direction.

## 10.7 Founder and organizational intelligence

In deeptech, the company is not only a bundle of assets. It is a learning system operating under scientific, capital, and market uncertainty. Founders and employees determine how quickly the organization notices errors, changes direction, recruits missing capabilities, and turns technical progress into a product.

AutoNext should therefore model:

```text
founder beliefs
    -> strategic decisions
    -> irreversible commitments
    -> people hired and organization designed
    -> employee behavior and operating culture
    -> technical/commercial outcomes
    -> founder learning or denial
```

The useful question is not “Is this founder impressive?” It is:

> Does this team form non-obvious but accurate beliefs, convert them into coherent action, learn faster than the problem changes, and build an organization capable of delivering the promised outcome?

### Founder belief and decision ledger

For each founder, record dated statements and actions separately:

- problem definition and why it matters;
- contrarian or non-consensus belief;
- view of the customer and route to market;
- technical architecture choice;
- build-versus-partner decision;
- capital and sequencing philosophy;
- hiring and organizational choices;
- predictions with an observable resolution date;
- moments when the founder changed their mind;
- irreversible commitments of money, reputation, time, or architecture;
- subsequent outcome.

This creates a decision record:

```json
{
  "founder_id": "person-17",
  "belief": "Packaging, not the photonic die, will determine commercial performance",
  "stated_at": "2024-06-10",
  "source_id": "source-441",
  "decision": "Built an internal packaging team before scaling sales",
  "commitment": "Hired 14 packaging and reliability engineers",
  "expected_observable": "Qualified packaged module",
  "resolution_window": "2025-Q4/2026-Q2",
  "outcome": "pending",
  "confidence": 0.78
}
```

The system can then distinguish originality from hindsight storytelling. A differentiated claim made before the result is more informative than a polished explanation offered afterwards.

### Founder dimensions

Use evidence-backed dimensions rather than a single founder score:

- **Problem originality** — does the founder frame the problem differently in a way that changes action?
- **Technical depth** — can they reason across mechanism, implementation, and failure modes?
- **Strategic coherence** — do product, customer, capital, hiring, and distribution choices reinforce the same thesis?
- **Learning velocity** — do beliefs update when reality disagrees?
- **Truth orientation** — are limitations and failures described specifically, or obscured by narrative?
- **Capital judgment** — are experiments sequenced to resolve the most valuable uncertainty per unit of capital?
- **Talent magnetism** — can the founder recruit people who could work elsewhere?
- **Delegation and institution building** — can capability exist beyond the founder?
- **Integrity and stakeholder behavior** — consistency between promises, contracts, ownership, attribution, and conduct.
- **Resilience with adaptation** — persistence in the purpose without blind attachment to the first implementation.

“Different thinking” only receives credit when it produces a testable decision, an advantage, or a useful learning loop. Eccentricity, confidence, prestige, and charisma are not substitutes.

### Leadership configuration, not CEO stereotype

AutoNext should not award a mechanical bonus for a STEM degree or a penalty for a sales background. It should assess whether the leadership system gives the right kinds of truth real authority.

The required functions are:

1. **Technical truth** — someone can judge the mechanism, architecture, limits, and failure modes without relying entirely on internal advocates.
2. **Product judgment** — someone decides which capability should become an experience or workflow.
3. **Customer and distribution truth** — someone has direct access to adoption friction, procurement, willingness to pay, and channel power.
4. **Capital and operating discipline** — someone sequences experiments, manufacturing, hiring, and financing without destroying the option value of the company.
5. **Integration authority** — the company can resolve disagreements among these functions without allowing narrative, hierarchy, or quarterly pressure to suppress inconvenient facts.

For each company, record:

- who owns each function;
- whether that person has formal decision rights and board access;
- whether leaders can understand one another's evidence;
- examples of technical dissent reaching a consequential decision;
- examples of customer evidence changing the technical roadmap;
- whether the configuration matches the company's current phase;
- succession risk if one integrator leaves.

The expected phase pattern is a hypothesis to test, not a universal law:

| Phase | Leadership capability most likely to be binding |
|---|---|
| Scientific uncertainty | Technical truth and experiment selection |
| Technology-to-product translation | Technical/product integration |
| Qualification and first market | Customer access plus technical credibility |
| Scale and manufacturing | Operations, quality, capital, and systems |
| Category expansion | Architecture renewal plus distribution |

The risk from a commercially led team is not that selling is bad. It is selling a reality the organization cannot yet produce, allowing near-term customer requests to fragment the architecture, or suppressing technical bad news. The risk from a technically led team is not that engineering is bad. It is optimizing the artifact while missing procurement, workflow, capital, regulation, or the customer's actual definition of value.

AutoNext should therefore report a **leadership complementarity map**, a **technical-truth authority score**, and a **phase-fit assessment**—not a single “technical founder” score.

### Employee and organization signals

Employee evidence can reveal whether the founder's stated strategy exists inside the company. Useful signals include:

- senior technical and commercial hires;
- which functions are growing or shrinking;
- tenure and regretted attrition in critical teams;
- whether strong employees follow the founder across companies;
- internal promotions versus perpetual external replacement;
- job descriptions that reveal hidden product or manufacturing priorities;
- concentration of hiring around a claimed bottleneck;
- former-employee accounts of decision speed, technical standards, customer contact, and management behavior;
- consistency or divergence across engineering, sales, operations, and leadership accounts;
- how themes change before and after restructurings, financing events, failed milestones, or leadership transitions;
- alumni quality and whether former employees become founders or trusted industry operators.

The system should not use the average rating from an employee-review site as a culture score. It should analyze dated themes, function, tenure, sample size, and corroboration.

### Source hierarchy

Higher-value sources include:

1. dated founder interviews, technical talks, shareholder letters, blogs, podcasts, and internal-style operating documents made public;
2. actions visible through hiring, acquisitions, facilities, patents, publications, product releases, partnerships, and capital allocation;
3. direct references and expert interviews collected with consent;
4. employee and former-employee public statements;
5. job postings and aggregate talent-flow data;
6. anonymous review sites and social posts, treated as weak leads unless patterns are independently corroborated.

Private individuals' personal data should not be collected merely because it is accessible. AutoNext should retain only professional, decision-relevant information with source provenance and appropriate usage rights.

### Employee-signal normalization

Each employee observation should record:

- source and date;
- current or former employee;
- function and seniority when public;
- approximate tenure period;
- firsthand versus hearsay;
- positive, negative, or mixed theme;
- whether the statement concerns a local manager or company-wide behavior;
- corroborating and contradicting observations;
- potential selection, recency, litigation, or retaliation bias;
- confidence and whether it can affect a score.

Repeated independent themes matter more than vivid anecdotes. A complaint from one team is not automatically evidence of an organizational property.

### Narrative-versus-behavior test

For every important strategic claim, compare words with observable commitments:

| Founder/company says | Behavioral evidence to seek |
|---|---|
| “Manufacturing is our moat” | manufacturing leadership, process hires, facilities, supplier agreements, yield disclosures |
| “Customers co-develop the product” | paid pilots, joint validation, customer engineering hires, repeat orders |
| “We are capital efficient” | milestone achieved per dollar, facility choices, dilution, grant leverage |
| “We empower exceptional people” | decision ownership, retention of strong leaders, internal promotions, alumni references |
| “We learned from the failure” | changed architecture, milestone sequence, hiring, governance, or capital allocation |

The gap between narrative and behavior is itself an investable signal.

### Human-intelligence agents

Add four specialist roles when sufficient evidence exists:

1. **Founder historian** — reconstructs beliefs, decisions, predictions, reversals, and outcomes over time.
2. **Organizational anthropologist** — synthesizes employee themes and how work is actually coordinated.
3. **Talent-network analyst** — maps critical hires, departures, alumni, and capability formation.
4. **Charisma-bias red team** — argues whether prestige, storytelling, or media visibility is being mistaken for evidence.

These agents must separate facts, reported perceptions, and inference. They cannot diagnose personalities or infer protected or medical traits.

### Human and organizational outputs

AutoNext should produce:

- founder belief timeline;
- decision and prediction scorecard;
- strategic-coherence map;
- organizational capability map;
- critical talent inflow/outflow timeline;
- employee-theme distribution with confidence and sample warnings;
- narrative-versus-behavior gaps;
- founder-dependence risk;
- succession and delegation assessment;
- three reference questions that would most reduce uncertainty.

### Terminal commands

```console
autonext founder timeline FOUNDER_ID
autonext founder decisions FOUNDER_ID --as-of 2026-11-16
autonext org map COMPANY_ID
autonext org talent-flow COMPANY_ID
autonext org employee-themes COMPANY_ID
autonext org narrative-gap COMPANY_ID
autonext compare COMPANY_A COMPANY_B --lens organization
```

This layer should influence company quality, execution probability, and confidence. It should not directly determine public-security attractiveness without also establishing valuation, materiality, and timing.

## 11. Photonics vertical

### 11.1 Taxonomy

- integrated photonics;
- optical interconnects and co-packaged optics;
- lasers and light sources;
- detectors, imaging, and sensing;
- LiDAR;
- photonic compute and accelerators;
- quantum photonics;
- semiconductor and lithography equipment;
- optical components, packaging, and test;
- enabling materials and manufacturing.

### 11.2 Technical evidence

The photonics module should capture domain-specific metrics without forcing every company into the same specification table:

- wavelength and spectral range;
- power, sensitivity, noise, loss, and efficiency;
- bandwidth, latency, and energy per bit or operation;
- integration platform and process node;
- packaging and thermal requirements;
- fabrication partner and manufacturing readiness;
- yield, reliability, lifetime, and environmental qualification;
- independent benchmarks and replication;
- patents and freedom-to-operate indicators;
- design wins, qualification stage, and shipped units;
- customer switching costs and system integration burden.

### 11.3 Fundamentals

For public companies:

- revenue and segment mix;
- gross margin and operating leverage;
- R&D intensity;
- capex and working-capital burden;
- cash, debt, dilution, and refinancing needs;
- customer and supplier concentration;
- valuation and market expectations;
- market price as of the run date;
- the next dated recognition catalyst.

For private companies:

- funding history and non-dilutive capital;
- estimated runway with confidence bounds;
- strategic investors and commercial partners;
- known orders, design wins, qualification, or revenue;
- manufacturing and scale capital required before the next milestone;
- ownership, founder provenance, and IP transfer;
- likely next financing or strategic outcome.

### 11.4 Do not conflate two meanings of technical analysis

- **Technical diligence** evaluates the underlying science and engineering.
- **Market technicals** evaluate price, volume, liquidity, and trading behavior for a public security.

They should be separate modules and separate scores. Market technicals are optional and never substitute for technical diligence.

## 12. Terminal experience

### Phase 1: composable CLI

Use Typer for commands and Rich for tables, progress, tracebacks, and Markdown rendering. Every interactive action must also have a non-interactive flag form so runs can be scripted and tested.

```console
# Create and validate a thesis
autonext thesis init photonics
autonext thesis validate photonics/thesis.yaml

# Build and inspect a universe
autonext universe build photonics --public --private --as-of 2026-11-15
autonext universe list photonics --show-exclusions
autonext universe resolve photonics --review-ambiguous

# Run or resume research
autonext run photonics --as-of 2026-11-15 --workers 8
autonext run resume RUN_ID
autonext run status RUN_ID

# Work with conclusions
autonext rank photonics --cohort public --profile evidence
autonext explain COMPANY_ID
autonext compare COMPANY_A COMPANY_B
autonext contradictions COMPANY_ID
autonext next-question COMPANY_ID
autonext diff RUN_OLD RUN_NEW

# Export
autonext export RUN_ID --format json
autonext export RUN_ID --format csv
autonext export RUN_ID --format markdown
```

### Phase 2: terminal UI

After the data contracts and CLI stabilize, add a Textual interface with:

- universe and rank table;
- filter and command palette;
- company dossier;
- evidence/contradiction pane;
- run progress and failures;
- thesis editor;
- old-run versus new-run diff.

The TUI calls the same application services as the CLI. It contains no unique research logic.

## 13. Run engine and reliability

The workflow is an explicit directed graph:

```text
define universe
    -> resolve entities
    -> collect sources
    -> normalize observations
    -> extract claims
    -> verify claims
    -> compute deterministic metrics
    -> score pillars
    -> generate counter-thesis
    -> rank
    -> export
```

Requirements:

- each step is idempotent;
- outputs are content-addressed where practical;
- a failed company does not fail the entire universe;
- runs resume from checkpoints;
- retries are bounded and provider-aware;
- concurrency is controlled per provider;
- every run records configuration, code version, model/provider versions, source versions, and thesis version;
- expensive language-model synthesis is limited to top candidates, contradictions, and ambiguous cases;
- deterministic retrieval and calculation run across the full universe.

Run states:

```text
pending -> running -> complete
                   -> partial
                   -> failed
                   -> cancelled
```

`partial` is a first-class result. The report lists missing providers, failed companies, and whether the rank is safe to use.

## 14. Storage

Use local-first storage:

- **SQLite** for canonical entities, run metadata, claims, evidence links, scores, overrides, and decisions.
- **Parquet** for large time series, filings tables, benchmark datasets, and provider snapshots.
- **DuckDB** as the local analytical query layer over Parquet and selected SQLite exports.
- **Filesystem object store** for immutable raw source snapshots and generated reports.

Suggested layout:

```text
~/.autonext/
  autonext.db
  objects/
  parquet/
  runs/RUN_ID/
    manifest.json
    errors.jsonl
    report.md
    ranking.csv
```

SQLite is sufficient for the first single-user version. PostgreSQL and remote object storage should only be introduced when multi-user writes or remote execution become real requirements.

## 15. Error handling

Errors are classified, not flattened into a generic failure:

- `identity_ambiguous`
- `source_unavailable`
- `provider_rate_limited`
- `point_in_time_violation`
- `parse_failed`
- `claim_conflict`
- `insufficient_evidence`
- `analyzer_failed`
- `model_output_invalid`
- `thesis_schema_invalid`

The terminal output must show the impact of an error. For example: “Two companies lack patent data; their IP pillar is unknown and the evidence-adjusted rank has been recomputed.”

## 16. Testing and validation

### Unit tests

- point-in-time filtering;
- company/security identity resolution;
- score and coverage calculations;
- gate behavior;
- analyst override audit trail;
- provider normalization;
- date and currency normalization.

### Contract tests

Each adapter is tested against recorded fixtures. A provider response change should fail at the adapter boundary, not corrupt the canonical model.

### Golden-company tests

Select five photonics companies with hand-reviewed dossiers. Every release compares extracted claims, metrics, gates, and ranks against the curated expected output.

### Historical tests

Re-run selected companies at old `as_of` dates and assert that later filings, papers, prices, and announcements do not leak into the result.

### Ranking sensitivity

Display how rankings change when weights move within a reasonable range. A company that moves from first to twentieth under a small weight change is not a robust number-one conclusion.

## 17. Patterns to borrow from current open-source work

### OpenBB

Borrow the provider-abstraction idea: commands depend on normalized data contracts, while provider-specific code stays behind adapters. Do not copy its breadth into the MVP.

### TradingAgents

Borrow point-in-time discipline, checkpoint resume, run isolation, recorded settings, and explicit specialist roles. Do not make a non-deterministic multi-agent debate the owner of the final rank.

### AI Hedge Fund

Borrow the mandate concept, local-first terminal workflow, persistent decision history, and tamper-evident research/decision ledger. Avoid its simulated portfolio surface until AutoNext's research output is trustworthy.

### Textual

Use it for the later terminal UI because it supports asynchronous work, data tables, trees, command palettes, testing, and a possible browser-served interface. Keep the initial application usable without a full-screen TUI.

## 18. Build sequence

### Milestone 0 — contracts and fixtures

Deliverables:

- canonical Pydantic models;
- thesis schema;
- run manifest;
- five golden photonics companies;
- recorded fixtures from Scout, Assay, and Conviction.

Exit test: one company dossier can be assembled reproducibly from fixtures with no language model.

### Milestone 1 — photonics research run

Deliverables:

- Typer/Rich CLI;
- SQLite evidence ledger;
- Scout universe adapter;
- Assay verification adapter;
- manual CSV/JSON fundamentals import;
- thesis scoring, coverage, gates, ranking, and explanation;
- JSON/CSV/Markdown export.

Exit test: a 25-company photonics universe completes, resumes after interruption, and every score resolves to evidence.

### Milestone 2 — live fundamentals and adversarial review

Deliverables:

- public filings and market-data adapters;
- private funding/grant normalization;
- structured investment committee built from the `lab-signal` panel pattern;
- blind first-round memos, bull/bear cases, cross-examination, and belief revision;
- Conviction counter-thesis and decision-history integration;
- founder belief/decision ledger and Assay provenance integration;
- dated founder statements, observable commitments, critical hires, and narrative-versus-behavior checks;
- employee-signal schema with source-quality and sample-bias controls;
- dated catalysts and the three clocks;
- old-run/new-run diff.

Exit test: a point-in-time public-company run can be reproduced and audited without future leakage.

### Milestone 3 — causal market intelligence

Deliverables:

- architecture-transition records;
- actor, incentive, constraint, value-chain, and profit-pool graph;
- first-, second-, and third-order causal edges with lags and falsifiers;
- scenario engine with continuation, transition, bottleneck-shift, capital-cycle, and incumbent-capture worlds;
- separate technology, company-quality, venture-investment, and public-security rankings;
- public expectations-gap and private-to-public bridge analysis;
- pairwise comparison of top candidates.

Exit test: a technical state change can be traced through three orders of consequence to specific company economics and public recognition, with every arrow linked to evidence or marked as a hypothesis.

### Milestone 4 — scale and research prioritization

Deliverables:

- incremental refresh;
- provider caches and budgets;
- expected-value-of-information queue;
- rank sensitivity;
- Textual TUI;
- scheduled sector refreshes.

Exit test: hundreds of companies can be refreshed incrementally while expensive analysis is restricted to the highest-value unknowns.

### Milestone 5 — additional verticals

Add semiconductors, space, biotechnology, batteries, and quantum only after the photonics contracts survive real use. Each new vertical must contribute taxonomy, metrics, analyzers, golden companies, and a thesis profile.

## 19. Key trade-offs

### New repository versus extending Conviction

**Recommendation: new repository.** Conviction is a decision journal and adversarial thesis system. AutoNext is a batch intelligence and evidence system with a Python-heavy scientific/data stack. Keeping the boundary explicit prevents Conviction from becoming an unmaintainable monolith. The two can later share a terminal entry point.

### Python versus TypeScript

**Recommendation: Python for AutoNext.** Assay is already Python, and the strongest ecosystem for filings, scientific data, numerical analysis, DuckDB, Parquet, and terminal research is Python. Continue using Scout and Conviction as services rather than porting them.

### Workflow library versus small in-process engine

**Recommendation: start small.** A persisted step table, explicit DAG, bounded async workers, and content hashes are enough for the first version. Introduce Dagster, Prefect, or a queue only when remote workers or complex schedules require them.

### One rank versus several views

**Recommendation: several views plus an optional composite.** The system should help the user make a judgment, not hide judgment inside false precision.

### Automated entity resolution versus human review

**Recommendation: automate high-confidence matches and queue ambiguous ones.** Identity errors propagate into every later conclusion and deserve a deliberate review surface.

## 20. Decisions to revisit later

- Whether the CLI should ultimately be a subcommand of `conviction` or remain `autonext`.
- Which paid fundamentals and private-market providers are justified by coverage and licensing.
- Whether source snapshots can be retained locally under each provider's terms.
- Whether team collaboration requires PostgreSQL and object storage.
- Whether market technicals improve decisions enough to remain in the core product.
- Whether portfolio construction belongs in AutoNext or remains a separate consumer of its outputs.

## 21. Recommended immediate implementation

Create `C:\Users\shibi\repos\autonext` as a standalone Python project and implement Milestone 0 before adding live providers. Use photonics as the forcing function and select five golden companies across different business architectures: a component supplier, an integrated-system company, a semiconductor-equipment company, a photonic-compute company, and a sensing company.

The first demonstration should be intentionally narrow:

```console
autonext run photonics --fixture-set golden-v1 --as-of 2026-11-15
autonext rank photonics --cohort public
autonext explain COMPANY_ID
```

If those three commands are trustworthy, the system has a foundation. If they are not, a richer interface or more agents will only make the uncertainty harder to see.

## 22. High-leverage extensions

The following additions should be prioritized by their ability to improve decisions and learning, not by how impressive they look in a demonstration.

### 22.1 Close the learning loop

Most research systems stop at a recommendation. AutoNext should continue until the forecast resolves:

```text
observe -> explain -> predict -> freeze -> decide
        -> monitor -> resolve -> score -> update
```

Every material forecast needs:

- probability range;
- resolution date or window;
- observable success and failure conditions;
- evidence available at freeze time;
- actual outcome;
- forecast error;
- which causal edge, assumption, agent, or human judgment was wrong.

Track Brier scores for binary forecasts, interval coverage for dates and values, rank correlation, and calibration by sector, evidence type, agent role, and analyst.

### 22.2 Separate confidence from conviction

- **Confidence** describes how well supported and certain the belief is.
- **Conviction** describes the attractiveness of the decision after considering price, payoff asymmetry, time, downside, and portfolio context.

A low-probability outcome can be a high-conviction investment when the payoff is sufficiently asymmetric. A highly certain technology trend can be an unattractive investment when it is fully priced.

### 22.3 Maintain rejected alternatives and counterfactuals

Freeze the full shortlist, rejected companies, reasons, and equal-weight comparison. Later distinguish:

- architecture/thesis alpha;
- model ranking alpha;
- human selection or taste alpha;
- sizing alpha;
- timing alpha.

Without rejected alternatives, every successful selection can be explained after the fact and judgment never becomes measurable.

### 22.4 Evidence independence graph

Ten articles repeating one company press release are one source, not ten confirmations. AutoNext should trace source ancestry and assign an independence group:

```text
company announcement
  -> wire-service story
      -> trade article
          -> newsletter
```

Confidence should increase with independent corroboration, not citation volume.

### 22.5 Expected value of information

For every unresolved question, estimate:

- probability that the answer changes the decision;
- magnitude of the decision change;
- cost, time, and availability of obtaining the answer;
- whether the answer will arrive naturally before capital must be committed.

This produces a research queue that asks the most decision-relevant question next rather than collecting the most convenient data.

### 22.6 Market-implied expectations

For public companies, do not ask only what AutoNext believes. Estimate what must already be true to justify today's price:

- revenue, margins, market share, or capacity implied by valuation;
- probability of success implied by the security price;
- management guidance and consensus history;
- narrative density and attention;
- which assumption differs from the AutoNext thesis.

The investment exists in the gap between evidence and expectations, not in the quality of the company alone.

### 22.7 Capital-cycle and survival engine

Deeptech companies can be technically right and still lose because they run out of time or capital. Model:

- cash runway under scenarios;
- capex and working-capital requirements;
- dilution before value recognition;
- refinancing and covenant risk;
- capacity announcements across the industry;
- likely overbuild and price compression;
- who can finance through the down-cycle.

### 22.8 Competitive-response game tree

For a promising company, ask how every powerful actor can respond:

- copy;
- acquire;
- bundle;
- vertically integrate;
- cut price;
- lock distribution;
- influence standards or regulation;
- delay qualification;
- make the startup's complement free.

Rank the response by incentive, capability, cost, time, and historical behavior. A moat is partly the set of profitable responses competitors cannot execute.

### 22.9 Expert-interview cockpit

Convert the highest-value unknowns into role-specific interview guides for customers, suppliers, former employees, scientists, procurement officers, regulators, and manufacturing experts. After an interview:

- separate observation, opinion, and hearsay;
- link each note to claims and causal edges;
- record conflicts and source incentives;
- update only affected scores and agents;
- preserve consent, confidentiality, and MNPI/compliance boundaries.

### 22.10 Portfolio-level hidden dependencies

Several apparently different companies may depend on the same hidden variable: one customer, foundry, regulator, subsidy, interest-rate regime, material, clinical mechanism, or AI-capex cycle. Build an exposure graph and stress the portfolio by causal dependency rather than sector label alone.

### 22.11 Action ladder

The output should not force every conclusion into buy/hold/pass. Use a staged action set:

1. reject;
2. archive as interesting but non-investable;
3. research next question;
4. monitor a falsifiable milestone;
5. begin diligence or founder/customer outreach;
6. take a small option-sized position;
7. take a full position;
8. reduce or exit;
9. update the thesis without changing the position.

This preserves option value and separates “interesting” from “actionable now.”

### 22.12 Taste-learning layer

AutoNext should learn the user's judgment without merely imitating past choices. Compare the user's ranking with the systematic shortlist, capture the decisive qualitative reason, and later score whether the override added value. The aim is to discover where human taste is genuinely superior, where the model is superior, and where both are systematically blind.

### 22.13 Five operating modes

Keep the product understandable by organizing commands around five modes:

- **Explore** — discover architectures, companies, people, and anomalies.
- **Underwrite** — build a point-in-time company and security case.
- **Decide** — compare alternatives, size uncertainty, and choose an action.
- **Monitor** — detect evidence, catalyst, people, and expectation changes.
- **Learn** — resolve forecasts, audit mistakes, and recalibrate the system.

Every feature should belong clearly to one of these modes. Features that belong nowhere are likely scope creep.

### 22.14 The product's deepest moat

The long-term moat is not the number of agents or sources. It is the accumulated, point-in-time record of:

- what the system and analyst believed;
- why they believed it;
- which evidence was available;
- what decision was made;
- what happened;
- which reasoning pattern proved reliable.

That dataset becomes a personalized science of deeptech judgment.
