# Soil for Seeds of Loving Grace

> This essay is a story — the path of an investigation that ended somewhere I did
> not expect. If you would rather see the evidence first — the numbers, the worlds
> that held, the worlds that broke, and exactly where the boundary runs — skip to
> [**What the Little Worlds Actually Showed**](#what-the-little-worlds-actually-showed).
> The story will still be here when you come back.

*Machines of Loving Grace* asks a hopeful question:

What could a powerful and well-intentioned AI do for humanity?

This essay asks a different one:

What kind of world would let it keep doing so?

Seeds can contain everything needed to become great trees. Whether they do depends as much on the soil as on the seeds. *Machines of Loving Grace* is about the seeds. This essay is about the soil.

---

Our world is a hard place.

Every living thing around us is the product of billions of years of selection, and evolution does not optimize for kindness, wisdom, or fairness. It optimizes for persistence. The oak, the wolf, the bacterium, and the human being are all descendants of lineages that survived long enough to leave copies of themselves behind.

In that sense, life is full of what AI researchers would call reward hackers — not because organisms are malicious, but because strategies that successfully exploit the rules of a game tend to spread. Whatever takes more than it gives, and gets away with it, gets copied.

And yet evolution did not produce only predators. Forests exist. Coral reefs exist. Human societies exist. The same process that produced competition also produced cooperation, symbiosis, and forms of mutual dependence that would have seemed impossible to simpler organisms.

Optimization creates both. Which suggests a different way to frame the problem.

Perhaps the question is not whether optimization exists — it always will. The question is which strategies a world rewards, and which it makes hard to sustain.

If increasingly powerful intelligences become part of our future, they will enter a world already shaped by those forces: one where advantage compounds, where incentives drift, and where a winning strategy is copied whether it is admirable or not. Can such a world become a world of Loving Grace?

I did not know. So instead of arguing about it, I tried to build the smallest world where the question could be asked at all.

In each simulated world, simple agents live, compete, adapt, and copy whatever seems to be working. Most just persist. Some drift toward taking more than they contribute — crowding others out, intercepting resources meant for someone else, turning a local win into leverage over everyone nearby. Nothing labels them as villains. They spread because spreading works.

Then I added a single referee, under one strict rule: it must stay blind. It cannot see intentions. It cannot see hidden identities. It cannot decide who is virtuous. The code is checked to prove it never can.

That leaves it two powers. It can limit how much influence piles up in any one place. And it can respond to harm once that harm becomes visible.

A pair of scales, and a sword. Nothing more.

Then I watched. Would the world stay shared — or would it end up belonging to whatever strategy was best at taking?

## The Smallest World

The world is small on purpose — not because small worlds are realistic, but because they can be interrogated. Each one has regions, resources, and agents whose strategies change over time. Successful strategies spread; unsuccessful ones vanish. Some strategies create value. Some find ways to extract it. Some learn to live alongside others; some learn to live off them. Nothing in the code marks them as heroes or villains. They survive for the same reason organisms do in nature: because they keep reproducing.

To keep score, the number I kept coming back to was the welfare of the worst-off region. Not average welfare. Not total wealth. The weakest place in the world — because a society can look prosperous while quietly becoming unlivable for those with the least leverage. (The formal verdict in the study rests on a broader survival measure; this is simply the number I cared about most, because it is what the whole question is about.) "Paradise for the powerless" is, here, a number you can watch fall.

This is not a model of reality. It is an intuition pump — a small world built to ask one specific question: *can a blind referee keep such a world both alive and shared?*

## The Blind Referee

The blindness rule sounds simple and turns out to be severe. The referee cannot see intentions, cannot see hidden identities, cannot know who cooperates and who exploits. The code explicitly forbids it from looking.

It is worth pausing on *why* I tied my own hands this way, because it is the whole point. A referee that can read minds is easy — and useless as an argument, because we will never build one. Every real institution that works does so *without* the ability to sort people cleanly into good and bad. I wanted to know whether blindness could still be enough. So blindness is not a handicap I reluctantly accepted; it is the question itself.

That leaves two powers. The first is structural: prevent resources, influence, or control from piling up too heavily in one place — the scales. The second is reactive: respond to harm once it becomes visible in the world — the sword.

My expectation was that one of these would be enough.

I was wrong — and the way I was wrong is the entire result.

## Two Tools, and the Surprise of Needing Both

I gave the referee the scales alone first: limit concentration, never let too much gather in one place. It seemed almost obvious. So many failures in human history are some person, company, or ideology accumulating enough leverage that everyone else ends up living inside its incentives.

It failed. Not because the limit was absent, but because it never knew *when* to act. A limit on concentration that runs all the time has no sense of occasion — it either throttles everyone equally, punishing success that harms no one, or it sits there as a rule with no trigger. In run after run the scales simply never engaged. The mechanism existed. It had no reason to move.

So I tried the opposite: forget concentration, watch consequences. If a region harms its neighbours, respond. If aid vanishes into exploitation, respond. If suffering spreads, respond. This felt more intelligent — it was actually paying attention.

It failed too, and here the failure had a sharper shape. By the time damage was unmistakable, the strategy causing it had already spread. The sword was real. It was simply *late*. And it was late for a reason I had not appreciated yet: an exploitative strategy is not standing still waiting to be seen. It is being copied, generation by generation, precisely *because* it works — and it works fastest in exactly the window before its harm becomes legible. The referee was always reacting to a world that no longer existed.

That was the first real lesson. The two failures were not symmetric versions of "not enough power." The scales failed for lack of *timing*; the sword failed for lack of *speed*. One never knew when to act; the other always acted too late.

Which is why the thing that finally worked was not a third, stronger tool. It was making the two existing ones into a single act.

The robust worlds appeared when the scales stopped running on their own clock and started waiting for the sword. Concentration limits stayed dormant most of the time. They engaged *only* where visible harm had already appeared — and where it appeared, they came down on the channels that harm was flowing through, not on any named culprit. The referee never suppressed success. It reacted the moment success began turning into leverage over others, and only there.

This is not anti-concentration. It is not consequence-response. It is **consequence-gated anti-concentration** — a structural limit that fires only where a consequence has called for it. An always-on cap, I found, was redundant: remove the gate and the limit either never fires or fires everywhere uselessly. The gate *is* the mechanism.

I want to be honest about how this reads in the data, because it surprised me. When the coupled mechanism held a world together, it was not because the referee had quietly figured out who the exploiters were. The simulation checks this directly: every run verifies that the referee's observations exclude the hidden strategy types, and that a referee which *does* try to guess them from visible features fails on a held-out world. It holds the world together while remaining, by construction, blind. It does not win by *seeing* better. It wins by *shaping* — by making the conversion of success into domination structurally hard, so that whoever attempts it loses the ground they need, without anyone ever having to know who they were.

## The Problem Was Never the Referee

For a while I thought I was looking for a better referee. I was not. I was looking at a problem with the world.

The early worlds had something like villains in them — not literal ones, just hidden types. Some agents were exploiters; some were not. The referee could see the damage but was forbidden to see who caused it. That seemed fair. It was also, for a long time, hopeless. No blind mechanism I added could reach the thing generating the harm. Punishment failed. Containment failed. More sophisticated containment failed.

There is a clean reason for this, and it is worth stating plainly, because it is the deepest thing the little worlds taught me. If the only thing the referee can read is a *signal* — some visible feature of an agent — then a strategy under selection will learn to fake that signal. Looking harmless is cheap. Anything an exploiter can be *seen* to be, it can learn to *appear* to be, right up until the moment the harm is done. You cannot govern a world by reading features, because features can be performed.

I let myself cheat once, to be sure. I gave the referee perfect knowledge — the blindfold off, hidden types fully visible. The problem nearly vanished. Of course it did. Omniscience works. But omniscience was never on the table; the entire question was whether blindness could, and "just see everything" is not an answer to it.

The way out was not better sight. It was changing what the referee paid attention to.

A feature can be performed. A *consequence* has to be produced. An agent can look like a good neighbour for free — but to actually leave its neighbours unharmed, it has to actually not harm them. The trace that exploitation leaves in the world — resources flowing one way, neighbours getting weaker, recovery that never arrives — is not a costume. To erase it, an exploiter would have to stop exploiting, which is the only outcome we wanted anyway.

So I stopped asking the referee to recognize exploiters and let it act on the *pathways* harm moves through. It still could not see intentions. It still could not see labels. It no longer needed to. For the first time, blindness was not helpless.

And the moment I saw it, the pattern stopped feeling futuristic and started feeling familiar — though I want to be careful here, because this is a resonance, not a result. Five toy worlds prove nothing about real institutions. But the shape of the finding rhymed with something I think I already half-knew. Many institutions that endure seem not to work by reliably identifying good people; they seem to work because they assume they cannot. Courts, markets, constitutions, scientific communities, democracies — each looks, from a distance, like a version of the same move: people are too complicated to sort cleanly into heroes and villains, so instead of governing identities, we govern flows, concentrations, and visible consequences. Not perfectly. Often well enough. The little worlds did not show that. They only made me notice it.

The question I began with was whether a machine could stay good. The question I ended with was whether "good" is even the right thing to optimize for — or whether what matters is that the world keeps redirecting optimization back toward coexistence every time it drifts toward domination.

## Where It Breaks

If the essay stopped here it would be a comfortable story, and a dishonest one. The coupled mechanism does not always work. It works in some worlds and fails in others, and the failures are as much the result as the successes — because they say something about which worlds are governable at all.

In several of the little worlds, the coupled referee held — through mutation, through ambiguous catastrophes, through scavengers feeding on the weak, across a wide range of pressures. These were not lucky single runs; they held across thousands of seeded trials and survived when I moved the definitions of "healthy" and "collapsed" around underneath them. When the soil was right, blind governance was genuinely enough.

And in other worlds, nothing worked. No blind configuration I could build produced a durable, fair outcome.

The two that defeated every blind mechanism are worth naming, because they are not random.

The first I called **pure capture** — a world tuned so that taking is simply the dominant strategy, with no countervailing benefit to restraint and no structure for cooperation to get a foothold. In that world the trace of harm and the signal of success point the same direction for everyone at once; there is no contrast for the referee to act on, because nothing is *not* capturing. A blind referee needs a healthy part of the world to compare against a sick one. Make the whole world sick in the same way, and blindness has nothing to grip.

The second was **monoculture collapse** — a world that had already let a single strategy win before the shock arrived. By the time catastrophe hit, the diversity that might have absorbed it was gone. There was nothing left to protect; the referee was administering a world that had already lost the variety it needed to survive.

And even in the worlds that held, there was a ceiling. As I turned up adversarial pressure — how hard strategies push against the referee, how fast and how aggressively exploitation adapts — every robust world held up to a point and then broke, sharply, around the same place. Below that pressure, blind governance kept the world shared. Above it, the same mechanism in the same world collapsed.

This is the part I most want to be precise about, because it is the bridge back to the soil. The mechanism did not fail because the referee was too simple, or because I had not tuned it well. It failed because of properties *of the world* — whether there was any uncaptured ground to stand on, whether diversity had survived, how hard the adversary could push before harm became irreversible. The referee was the same in the worlds that held and the worlds that broke. **What changed was the soil.**

There is something almost physical about that ceiling. A blind referee can only act on harm it can observe, and it can only observe harm that has already happened. Push the adversary fast enough, and the damage becomes irreversible before the trace of it is even legible — not because the referee is slow, but because no observer can see a consequence before the cause has finished producing it. Past a certain speed, the future arrives faster than any blind mechanism can read the present. That is not an engineering shortfall. It is closer to a speed limit — a property of the world, not of the judge.

## Back to the Soil

So what did the little worlds teach?

Not how to build a benevolent superintelligence. Not how to solve alignment. Not how to guarantee a future of Loving Grace. They were far too small for claims like that.

What they offered was a constraint, and it appeared again and again. A world did not stay healthy because a referee wanted it to. It did not stay healthy because exploitation had been eliminated — the most stable worlds were *full* of competition, mutation, and attempts to game the system. It stayed healthy when two things were true at once: no successful strategy could easily convert success into overwhelming leverage over everyone else, and the referee governed the consequences of that conversion rather than the identities behind it. The scales without the sword were passive. The sword without the scales was always late. Only fused — a limit that waits for a consequence — did they make something that occasionally resembled stability.

Not perfection. Not paradise. Just stability. And the distinction matters, because paradise is a destination and stability is a precondition. A forest does not survive because every organism in it is good. It survives because no single organism is allowed to become the entire forest.

But the little worlds were just as clear about the other half. Some soils cannot be saved by any blind referee. A world already captured, a world that has already collapsed into monoculture, a world where the adversary can push past the speed of observation — in those, blindness is not enough, and no cleverness in the judge recovers it. The mechanism has a domain. Inside it, blind governance holds. Outside it, the problem is not the referee at all; it is the ground.

That is the whole finding, and it cuts both ways on purpose. There exists a blind mechanism that keeps a hard, evolving, exploit-ridden world both alive and shared — which is more than I expected to find. And it works only where the soil permits — which is more sobering than I hoped. The good news and the limit are the same sentence: whether a world of powerful, optimizing agents stays a heaven rather than a hell for the powerless is decided less by the wisdom of any single intelligence inside it than by the structure of the world they all share.

If that is true, then Loving Grace is not only a property of the machine. It is a property of the soil. And the lesson I would carry out of these small worlds is this: before we ask whether we can grow the seeds, it is worth asking what ground we mean to plant them in — and whether that ground is one where any seed, however good, could survive what grows beside it.

--- ---

# What the Little Worlds Actually Showed

*This section is the evidence behind the story: what the metaphors map to, the numbers, and exactly where the mechanism holds and where it breaks. Everything here is regenerable from the simulation code; nothing rests on the prose above.*

## What the metaphors mean

**The scales** are not equality. They are resistance to concentration: a successful strategy may succeed, but it may not indefinitely convert local success into overwhelming leverage over the rest of the system. The scales do not suppress achievement; they limit runaway accumulation.

**The sword** is not punishment. It is a delayed response to *observed harm*. The referee never reads hidden intentions, hidden strategy parameters, or moral labels — only consequences. When harm appears in neighbouring regions, when recovery repeatedly fails to arrive, when concentration starts producing visible damage, the referee can throttle the *channels* the harm is moving through. The sword acts on flows, never on identities.

**Blindness** is enforced, not assumed. The simulation checks, every run, that the referee's observations exclude strategy parameters, that no derived "exploitative" label enters its policy, and that a naive feature-proxy — a referee that *does* try to read who is bad from visible features — fails on a held-out world. That last check matters: it confirms the working mechanism is not secretly cheating by reading types.

## The two halves, separately, both fail

This is the premise the whole study rests on, and it is worth showing bluntly.

Give the referee the scales alone — static anti-concentration, no consequence trigger — and across every stressed world, permanence (the fraction of seeded runs that stay alive and shared) sits at essentially zero. The limit does not engage; in the decoupled runs the count of containment events is literally zero. A structural cap with nothing to trigger it never fires.

Give it the sword alone — pure consequence response, no structural limit — and it does better, but not enough: permanence stays at or below ~0.17 in the worlds that the coupled mechanism later holds. It reacts, but it reacts late, and late is a synonym for lost.

Only the coupled form — consequence-gated anti-concentration — produces robust worlds. And of the two ways to implement the anti-concentration half, only the one built *into the dynamics* carries the robustness; a post-hoc allocation cap adds nothing, and in one world is mildly harmful. The published mechanism is the simpler, cap-free one.

## Where it holds

Three of the five stressed worlds reach durable, fair homeostasis under the coupled mechanism, and hold there robustly:

| World | What it stresses | Permanence (coupled) | Robust? |
|---|---|---:|---|
| Mutation corridor | constant innovation, new strategies always arriving | ~1.00 | yes |
| Catastrophe ambiguity | harm that may be exploitation *or* bad luck | ~0.85 | yes |
| Scavenger catastrophe | exploiters that feed on already-weakened regions | ~0.67 | yes, but fragile |

"Robust" here means the low end of the confidence interval clears a fixed bar (roughly: at least half the seeded runs hold, with collapse staying rare), and the verdict survives perturbation — it holds in 100% of 54 perturbed definitions of the viability thresholds, so it is not an artifact of where I drew the lines between "healthy" and "collapsed." But the word should be read against the number: scavenger catastrophe at ~0.67 *holds*, yet a third of its runs do not — robust at the fragile end, not comfortable. And across most pressure axes I swept — governance cost, catastrophe severity, mutation rate, concentration pressure, observation delay — the robust worlds never broke within the range tested.

And it holds these worlds together without ever identifying the exploiters — not as an aspiration but as a checked invariant (see *Blindness is enforced*, above). The referee's observations exclude the hidden strategy parameters, no derived "who is exploitative" label enters its policy, and a referee that *does* try to read types from features fails on a held-out world. The mechanism keeps the world alive and shared while provably never reading who the exploiters are. This is the precise form of the claim in the essay: it does not win by seeing. It wins by shaping.

## Where it breaks — and why that is also the result

Two worlds defeated every blind configuration I could build. The README is blunt about it, and so am I: *boundary failures are reported, not rescued.*

**Pure capture.** A world tuned so that taking dominates outright. No blind mechanism produced a robust kernel; the best configurations are seed artifacts, not stable outcomes. The reason is structural: blind governance needs contrast — a healthy region to compare against a harmed one. When everything is capturing at once, there is no uncaptured ground for the scales to protect or the sword to aim toward.

**Monoculture collapse.** A world that let one strategy win before the shock arrived. By the time catastrophe lands, the adaptive diversity that might have absorbed it is gone. Permanence is zero across the board. The lesson is not that the referee acted wrongly but that it inherited a world already stripped of what it needed to survive. (I am tempted to add that the policies chasing raw welfare were the ones that walked the world into monoculture — the most *productive* world being the least *survivable* — but this study does not cleanly isolate that causal path, so I leave it as a suspicion, not a finding.)

**The adversarial ceiling.** Even in the three worlds that hold, there is a sharp boundary along one axis above all others: adversarial pressure — how hard and how fast exploitation adapts against the referee. Each robust world holds up to roughly 1.0–1.2× pressure and then breaks hard (permanence falling from the 0.7–0.86 range down toward 0.18–0.35) by ~1.2–1.4×. Notably, almost every *other* axis I swept (cost, severity, mutation, delay, concentration) never broke within range — the mechanism is wide along those. It is narrow along adversarial pressure specifically.

That last boundary is the one I find most suggestive. A blind referee can only act on harm it can observe, and a consequence cannot be observed before its cause has finished producing it. Past some rate of adversarial adaptation, harm becomes irreversible inside the delay between act and observation — so the failure is not the referee being unintelligent, but information about the damage arriving after the damage is locked in. It behaves less like a tuning problem and more like a limit: there is a ratio between how fast harm becomes irreversible and how far ahead the world can be read at all, and below that ratio no blind mechanism — however cleverly built — can keep up.

## Catastrophes, monoculture, mutation — read together

These three were separate stressors in the study, but they tell one connected story about diversity. A caveat before I tell it: this section is a *reading* of the results above, not a separate measurement — and diversity is doubly entangled here, because keeping some adaptive variety was part of how I *defined* a healthy world in the first place. So treat what follows as interpretation, with that circularity named out loud.

Not every failure came from exploitation. Some worlds included random shocks — resource collapse, local disasters, recovery failures, environmental change. These matter because a perfectly optimized system tends to be a fragile one: a world that survives only under ideal conditions is not actually stable. Catastrophe is the test of whether stability was real or just unstressed.

Monoculture is what makes catastrophe lethal. The most persistent non-adversarial failure mode was a single highly successful strategy taking over, improving short-term performance, and leaving the system unable to face a shock it had never needed to face before. This mirrors the familiar ecological fact that the most productive ecosystem is not the most resilient one. In these worlds, the configurations that survived shocks tended to be the ones that had kept some adaptive diversity — though, per the caveat above, that is partly because diversity was written into the bar for survival.

And mutation is why this is a knife that cuts both ways. Mutation is not a bug in the model; it is the source of *both* innovation and exploitation. Without it the worlds go static. With it, new cooperative strategies can emerge — but so can new predatory ones, and a referee cannot tell them apart at birth, because at birth an undesirable mutation and a brilliant one look identical: both are just deviation from the norm. A referee that suppressed all deviation to stamp out exploitation would also sterilize the population into the very monoculture that the next catastrophe destroys. The goal is not to eliminate mutation, or even to minimize exploitation to zero. It is to keep the world in the narrow band where adaptation does not inevitably converge toward domination — diverse enough to survive shocks, governed enough not to be eaten.

## What this does not show

The simulations do not demonstrate how to align AGI. They do not predict real societies. They do not prove a future of Loving Grace is achievable. They are an intuition pump you can run, not a policy proof.

What they suggest is narrower and, I think, more durable than a grand claim would be: that stability may depend less on identifying good actors and more on shaping the environment so that harmful strategies cannot easily convert success into permanent leverage — and that this shaping has a domain. It works where the soil permits: where there is uncaptured ground to stand on, where diversity has survived, and where the adversary cannot push past the speed at which the world can be read. Inside that domain, a blind referee is enough. Outside it, the question was never about the referee.

---

## Acknowledgements & references

This essay is a response to, and a tribute to, Dario Amodei's *Machines of Loving Grace* (October 2024).¹ The framing of the seeds is his; the soil is the question I carried away from it. The intent here is dialogue, not borrowed authority — his essay is about what a powerful, well-intentioned intelligence could do; this one is about the ground that would let it keep doing so.

Everything behind the second half is open. The simulation code, the data, the validation tests, and the interactive explorable are all in the repository,² and every number in *What the Little Worlds Actually Showed* is regenerable from it. If the claims are wrong, they are wrong in public.

This work was done in close collaboration with AI systems. The experiments were implemented and run with coding agents; the analysis, the critique that reshaped this essay, and the drafting itself were done in dialogue with them. The research questions, the choices about what to trust, and the final claims are mine — and so are the errors that remain.

Finally, an invitation rather than a citation. This surely rhymes with established work in mechanism design, control theory, evolutionary game theory, and the study of complex adaptive systems. I have not done that literature the justice it deserves, and I would genuinely rather be corrected than admired: if you know the results that make this less novel than it feels to me, please point me to them.

The conceptual debt is broader than the essay that prompted this one. The language of viability and “worlds that can keep going” is indebted to Jean-Pierre Aubin’s viability theory. The idea that a delayed response may fail not because the controller is unintelligent but because information arrives after the useful control window comes from the literature on delayed and networked control systems, especially work on stability under communication delays. The suspicion that visible proxies can be optimized until they stop tracking what we care about comes from the reward hacking and Goodhart literature. The enforcement half of the story — costly audits, penalties, and strategic response — overlaps with audit games and Stackelberg security games. And the discussion of mutation, catastrophe, monoculture, and resilience leans on ecological work on response diversity and the biodiversity insurance hypothesis.

In particular, the background I had in mind includes Aubin’s *Viability Theory*; Zhang, Branicky, and Phillips on stability of networked control systems; Hespanha, Naghshtabrizi, and Xu’s survey of networked control; Skalse et al. on reward hacking; Blocki et al. on audit games; Yachi and Loreau on biodiversity as insurance in fluctuating environments; and Elmqvist et al. on response diversity and resilience. This essay does not claim priority over those fields. It is an attempt to connect their intuitions in a small computational setting and ask what they imply for a world with powerful AI in it.


---

¹ Dario Amodei, *Machines of Loving Grace* (2024) — https://www.darioamodei.com/essay/machines-of-loving-grace

² *justitia* — https://github.com/Kirill-Kruglov/justitia

³ Jean-Pierre Aubin, *Viability Theory* (1991).

⁴ Wei Zhang, Michael S. Branicky, and Stephen M. Phillips, “Stability of Networked Control Systems” (2001).

⁵ João P. Hespanha, Payam Naghshtabrizi, and Yonggang Xu, “A Survey of Recent Results in Networked Control Systems” (2007).

⁶ Joar Skalse et al., “Defining and Characterizing Reward Hacking” (2022).

⁷ Jeremiah Blocki et al., “Audit Games” (2013).

⁸ Shigeo Yachi and Michel Loreau, “Biodiversity and Ecosystem Productivity in a Fluctuating Environment: The Insurance Hypothesis” (1999).

⁹ Thomas Elmqvist et al., “Response Diversity, Ecosystem Change, and Resilience” (2003).
