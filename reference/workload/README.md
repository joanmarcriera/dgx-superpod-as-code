# Workload evidence pack: 2-SU DGX SuperPOD (63 x DGX H200 = 504 H200)

Retrieved 2026-09-30 from public web sources only. Convention: **QUOTED** = figure taken from the cited source
(via page fetch/summary; re-verify against the source before published use). **DERIVED** = my arithmetic.
**NOT FOUND** = could not be located; not invented. No PDFs were downloaded (SOURCES.csv is header-only).

## 1. H200 SXM vs H100 SXM (QUOTED)

Sources: [H200](https://www.nvidia.com/en-us/data-center/h200/), [H100](https://www.nvidia.com/en-us/data-center/h100/),
DGX H200 [datasheet](https://resources.nvidia.com/en-us-dgx-systems/dgx-h200-datasheet) (via search snippet).

| Metric | H100 SXM | H200 SXM |
|---|---|---|
| FP64 / FP64 Tensor | 34 / 67 TFLOPS | 34 / 67 TFLOPS |
| FP32 | 67 | 67 |
| TF32 Tensor (sparse) | 989 | 989 |
| BF16 / FP16 Tensor (sparse) | 1,979 | 1,979 |
| FP8 / INT8 Tensor (sparse) | 3,958 | 3,958 |
| Memory | 80 GB | 141 GB HBM3e |
| Bandwidth | 3.35 TB/s | 4.8 TB/s |
| NVLink | 900 GB/s | 900 GB/s |
| TDP | up to 700 W | up to 700 W |

NVIDIA's table footnote says Tensor figures are "with sparsity". DERIVED dense = half: TF32 ~494.5, BF16/FP16 ~989.5, FP8 ~1,979 TFLOPS
(dense values not shown on the pages fetched; standard 2:4 sparsity halving). Dense BF16 989 TFLOPS is the MFU denominator used below.

DGX H200 system (QUOTED, datasheet snippet): 8 x H200, 1,128 GB total GPU memory, 32 PFLOPS FP8 (sparse), 10.2 kW max,
8 x ConnectX-7 400 Gb/s IB/Eth, 4 x NVSwitch, 2 x Xeon 8480C (112 cores), 2 TB RAM.
DERIVED cluster totals (63 nodes / 504 GPUs): 71.1 TB HBM3e (504 x 141 GB); 504 x 4.8 = 2.42 PB/s HBM bandwidth;
504 x 989.5 = ~499 PFLOPS dense BF16 (~1 EFLOPS sparse); ~1.0 EFLOPS dense FP8.

**Where H200 gains:** compute is identical to H100; the gain is +76% capacity and +43% bandwidth (DERIVED: 141/80, 4.8/3.35).
So gains are in memory-bound work: long-context / large-batch inference (KV cache), fewer GPUs per model replica, less tensor/pipeline
parallelism in training. DERIVED examples: 70B BF16 weights (140 GB) fit one H200's 141 GB only barely (KV cache needs more, so FP8 or 2 GPUs);
405B at BF16 (810 GB) fits one 8-GPU H200 node (1,128 GB, ~318 GB left for KV) but not an H100 node (640 GB); 405B FP8 (~405 GB) fits 4 H200.
MLPerf corroboration: NVIDIA says H200 gave up to 1.5x H100 on data-centre inference ([v4.1 blog](https://developer.nvidia.com/blog/nvidia-blackwell-platform-sets-new-llm-inference-records-in-mlperf-inference-v4-1)),
and only ~14-16% on LoRA training ([v4.0](https://developer.nvidia.com/blog/nvidia-sets-new-generative-ai-performance-and-scale-records-in-mlperf-training-v4-0),
[v4.1](https://developer.nvidia.com/blog/nvidia-blackwell-doubles-llm-training-performance-in-mlperf-training-v4-1)).
Training is compute-bound, so H200 ~ H100 there.

## 2. MLPerf Training (QUOTED; official tables: https://mlcommons.org/benchmarks/training/)

I could not load the MLCommons results tables directly (dynamic page); figures come from NVIDIA/Nebius posts. System names/submission IDs: NOT FOUND.

| Round | Benchmark | System / GPUs | Time to train | Source |
|---|---|---|---|---|
| v5.0 | Llama 3.1 405B pretrain | Nebius, 512 x H200 + Quantum-2 IB | 244.6 min | [Nebius](https://nebius.com/blog/posts/industry-leading-ai-training-performance-in-mlperf) (post calls it "training step time"; ambiguity, treat as time-to-train per search summary, verify) |
| v5.0 | Llama 3.1 405B pretrain | Nebius, 1,024 x H200 | 124.5 min (1.97x scaling vs 512) | same |
| v5.0 | Llama 3.1 405B pretrain | NVIDIA Hopper, 512 GPUs | 269.12 min (GB200: 121.09 min) | [NVIDIA v5.0](https://developer.nvidia.com/blog/nvidia-blackwell-delivers-up-to-2-6x-higher-performance-in-mlperf-training-v5-0/) |
| v5.0 | Llama 2 70B LoRA | NVIDIA Hopper (H100), 8 GPUs | 27.93 min (unverified H200: 21.84 min) | same |
| v4.0 | Llama 2 70B LoRA | 8 x H200 | 24.7 min | [NVIDIA v4.0](https://developer.nvidia.com/blog/nvidia-sets-new-generative-ai-performance-and-scale-records-in-mlperf-training-v4-0) |
| v4.0 | Llama 2 70B LoRA | 1,024 x H100 | 1.5 min | same |
| v4.0 | GPT-3 175B | 11,616 x H100 | 3.4 min | same |
| v4.0 | GPT-3 175B | 512 x H100 | fetch summary said ~59 min (UNVERIFIED); v3.0 512 x H100 was 64.264 min per search summary | [techpowerup](https://www.techpowerup.com/323546/nvidia-mlperf-training-results-showcase-unprecedented-performance-and-elasticity) |
| v4.1 | GPT-3 175B | H100 at 256 GPUs referenced; times not given | NOT FOUND | [NVIDIA v4.1](https://developer.nvidia.com/blog/nvidia-blackwell-doubles-llm-training-performance-in-mlperf-training-v4-1) |

NOT FOUND: H200 GPT-3 175B results at 256-512 GPUs; H200 Llama 2 70B LoRA at 256-512 GPUs; v5.1 H200/H100 numbers (v5.1 and Llama 3.1 8B benchmark exist, see [MLCommons](https://mlcommons.org/2025/10/training-llama-3-1-8b/); not extracted).
Reading: the closest analogue to this cluster is 512 x Hopper on 405B = ~4-4.5 hours for the (short, to-target-loss) MLPerf run, NOT a full pre-train.

## 3. MLPerf Inference (QUOTED; tables: https://mlcommons.org/benchmarks/inference-datacenter/)

v4.1, 8 x H200 ([NVIDIA blog](https://developer.nvidia.com/blog/nvidia-blackwell-platform-sets-new-llm-inference-records-in-mlperf-inference-v4-1)):

| Model | Offline tok/s (8 GPU) | Server tok/s | DERIVED per GPU offline / server | H100 x8 (offline/server) |
|---|---|---|---|---|
| Llama 2 70B | 34,864 | 32,790 | 4,358 / 4,099 | not extracted (H200 up to 1.5x) |
| Mixtral 8x7B | 59,022 | 57,177 | 7,378 / 7,147 | 52,416 / 50,796 (H200 1.13x) |

Llama 3.1 405B H200 tokens/s: NOT FOUND (v5.0 blog gives only relative claims: GB200 NVL72 3.4x per-GPU vs 8-GPU H200;
[v5.0 blog](https://developer.nvidia.com/blog/nvidia-blackwell-delivers-massive-performance-leaps-in-mlperf-inference-v5-0)).
DERIVED upper bound: 504 x 4,358 = ~2.2 M tok/s Llama-2-70B offline if perfectly replicated (benchmark-tuned, not production SLA).

## 4. Why fabric matters: training vs inference

- QUOTED, NVIDIA RA ([network fabrics](https://docs.nvidia.com/dgx-superpod/reference-architecture/scalable-infrastructure-h200/latest/network-fabrics.html)): each 32-node SU is rail-aligned; "traffic per rail ... is always one hop away from the other 31 nodes in a SU"; 8 leaf + 4 spine per SU (compute fabric). Storage IB because per-node I/O must exceed 40 GB/s.
- Search-snippet (NVIDIA docs/blogs, verify): in a rail-optimised topology NIC-N of every DGX goes to the same leaf, which "helps maximize all-reduce performance while minimizing network interference". NCCL is topology-aware ([NCCL all-to-all blog](https://developer.nvidia.com/blog/doubling-all2all-performance-with-nvidia-collective-communication-library-2-12/)).
- Training: data-parallel gradient all-reduce/reduce-scatter and FSDP/ZeRO all-gathers cross nodes every step; MoE adds an all-to-all per layer. Paper evidence: EP all-to-all is 21-33% of iteration time on 400 Gbps IB ([mFabric, arXiv 2501.03905](https://arxiv.org/html/2501.03905v1)). Scale evidence: 405B MLPerf 512 -> 1,024 GPUs scaled 1.97x (above), which only happens on a non-blocking fabric.
- Inference: a model replica normally lives inside one node (8 GPU, 900 GB/s NVLink) so tensor-parallel traffic stays on NVLink; inter-node IB carries only request routing, and (if used) disaggregated prefill/decode KV transfer or multi-node 405B/MoE serving. NVIDIA doc that states this explicitly: NOT FOUND (this is my DERIVED reading from the architecture). Consequence: inference gains little from the full non-blocking fabric; training/MoE gains a lot.

## 5. Training arithmetic (DERIVED)

FLOPs = 6 x N x D (Kaplan et al.; standard rule). D = 15e12 tokens. Cluster peak = 504 x 989e12 = 4.985e17 FLOP/s (dense BF16).
Days = 6ND / (4.985e17 x MFU) / 86,400. MFU evidence (QUOTED): Llama 3 405B 43% (8K H100), 41% (16K), 38% (16K long-context)
([arXiv 2407.21783](https://arxiv.org/abs/2407.21783)); ByteDance MegaScale 55.2% on 175B / 12,288 GPUs ([arXiv 2402.15627](https://arxiv.org/abs/2402.15627)).
Assumed range 35-50%; BF16 (FP8 training could be faster but is not assumed).

| Model | FLOPs | MFU 35% | 40% | 45% | 50% |
|---|---|---|---|---|---|
| 8B | 7.2e23 | 47.8 d | 41.8 d | 37.2 d | 33.4 d |
| 70B | 6.3e24 | 418 d | 366 d | 325 d | 293 d |
| 405B | 3.645e25 | 2,418 d | 2,116 d | 1,881 d | 1,693 d |

Example line: 70B at 40%: 6.3e24 / (4.985e17 x 0.40) = 3.16e7 s = 366 d.
**Conclusion:** 8B on 15T is ~1-1.5 months; 70B on 15T is ~11-14 months (full run, one year-class); 405B on 15T is ~4.6-6.6 YEARS, i.e. not feasible on 504 GPUs.
Feasible instead: 70B on ~2-3T tokens (~50-75 d at 40%, DERIVED: 366 d x 3/15 = 73 d), or continued pre-training / domain adaptation, or MoE with small active params.
Also add realistic downtime: Llama 3 saw 466 interruptions in 54 days on 16K GPUs and >90% effective training time ([arXiv 2407.21783](https://arxiv.org/abs/2407.21783)); failures scale down with 504 GPUs but effective time <100% should be assumed.

## 6. Checkpoint arithmetic

QUOTED: mixed-precision Adam = 2Psi (fp16 weights) + 2Psi (grads) + K Psi (K=12: fp32 master + 2 moments) = 16Psi bytes ([ZeRO, arXiv 1910.02054](https://arxiv.org/abs/1910.02054)).
A recovery checkpoint needs weights + optimizer, typically 14 B/param (no grads); the 16 B figure is used here as a conservative upper bound.

| Model | Checkpoint @16 B/param | Write BW for 60 s | for 5 min | BF16 weights only (2 B/param) |
|---|---|---|---|---|
| 70B | 1.12 TB | 18.7 GB/s | 3.7 GB/s | 140 GB |
| 405B | 6.48 TB | 108 GB/s | 21.6 GB/s | 810 GB |

Checkpoint intervals: no authoritative number found (NOT FOUND). Meta's Llama 3 report only says checkpoint writes are bursty and they minimised GPU pause and raised frequency (per-GPU state 1 MB-4 GB; Tectonic 2 TB/s sustained, 7 TB/s peak). Common practice of 15-60 min (async checkpointing) is my uncited assumption.

QUOTED NVIDIA DGX SuperPOD H200 storage guidance ([storage architecture](https://docs.nvidia.com/dgx-superpod/reference-architecture/scalable-infrastructure-h200/latest/storage-architecture.html)):

| GB/s | Good | Better | Best |
|---|---|---|---|
| Single node read / write | 4 / 2 | 8 / 4 | 40 / 20 |
| 1 SU aggregate read / write | 15 / 7 | 40 / 20 | 125 / 62 |
| 4 SU aggregate read / write | 60 / 30 | 160 / 80 | 500 / 250 |

"Better" = compressed image/audio/text, "such as LLM training"; "Best" = large video/image, offline inference, ETL, datasets not cache-resident.
DERIVED for 2 SU (table gives only 1 and 4 SU; linear interpolation 2 x 1 SU): write 14 / 40 / 124 GB/s.
Reading: a 70B 5-min checkpoint (3.7 GB/s) fits any tier; 70B in 60 s (18.7 GB/s) needs Better or above; 405B in 60 s (108 GB/s) needs ~Best; 405B in 5 min (21.6 GB/s) is at the Better edge. Fast burst needs local NVMe/async staging, since the RA tiers are aggregate sustained figures.

## 7. Power and energy (DERIVED from QUOTED 10.2 kW/node)

- 63 x 10.2 kW = 642.6 kW DGX max. RA says rack power "exceeds 25 kW" ([architecture](https://docs.nvidia.com/dgx-superpod/reference-architecture/scalable-infrastructure-h200/latest/dgx-superpod-architecture.html)).
- Non-DGX IT (IB switches, Ethernet, storage, management): NOT FOUND in sources; assumption +10-20% -> ~710-770 kW IT. Facility PUE not assumed in the base numbers.
- 30-day run (720 h) at 80% average draw:
  - DGX only: 642.6 x 0.8 x 720 = 370,138 kWh = ~370 MWh.
  - With +15% other IT (assumed): ~426 MWh. With PUE 1.3 on top: ~553 MWh.

## 8. Buyer profiles (2025-2026)

- Sovereign AI: Sarvam AI (India) built 3B/30B/100B sovereign models with NVIDIA ([NVIDIA blog](https://developer.nvidia.com/blog/how-nvidia-extreme-hardware-software-co-design-delivered-a-large-inference-boost-for-sarvam-ais-sovereign-models/)); Outscale SecNumCloud sovereign HGX H200 ([Outscale](https://blog.outscale.com/en/outscale-accelerates-sovereign-ai-with-nvidia-hgx-h200-gpus-in-its-secnumcloud-infrastructure/)); a search snippet cited a sovereign project scaling 1,024->1,536 H200 for ~73 days FP8 pre-training (source unidentified, UNVERIFIED).
- Neoclouds: CoreWeave and Nebius run H200 clusters; Nebius validated NVIDIA Exemplar Cloud for H200 training and submitted 512/1,024 H200 to MLPerf ([Nebius](https://nebius.com/compute/h200), [CoreWeave](https://www.coreweave.com/products/hgx-h100-h200)).
- Turnkey 512 x H200 packages are sold to sovereign programmes, neoclouds and large enterprises ([DRACO 512xH200 listing](https://rdp.in/gpu-mart/product/draco-512x-h200-sxm-ai-supercluster/), vendor marketing).
- Enterprise foundation-model teams, universities: NVIDIA positions DGX SuperPOD (H200/B200) to "consolidate training, inference and analytics" ([SHI datasheet copy](https://www.content.shi.com/cms-content/accelerator/media/pdfs/nvidia/nvidia-030525-dgx-superpod-datasheet.pdf)); NextDC cites universities on H200 ([NextDC](https://www.nextdc.com/blog/universities-supercharge-ai-research-with-nvidia-h200)). Named enterprise 500-GPU buyers: NOT FOUND.

## Sources
NVIDIA H200 / H100 product pages; DGX H200 datasheet; DGX SuperPOD H200 RA docs (network fabrics, storage, architecture);
NVIDIA dev blogs for MLPerf Training v4.0/v4.1/v5.0 and Inference v4.1/v5.0; Nebius MLPerf v5.0 post; MLCommons benchmark pages;
arXiv 2407.21783 (Llama 3), 2402.15627 (MegaScale), 1910.02054 (ZeRO), 2501.03905 (mFabric); buyer-profile links in section 8.

## Evidence summary
- Full 15T-token pre-training is only realistic for ~8B (~1-1.5 months) on 504 H200; 70B takes ~11-14 months and 405B ~4.6-6.6 years (DERIVED, 35-50% MFU). Frontier-scale pre-training is out of reach; 70B at 2-3T tokens (~2-3 months) or continued pre-training is realistic.
- H200 = H100 compute with +76% memory and +43% bandwidth: the gain is in inference (up to 1.5x on MLPerf Inference) and large-model fit, only ~14-16% in training.
- 405B MLPerf at 512 Hopper GPUs takes ~4-4.5 h and scales 1.97x to 1,024 GPUs, which shows the non-blocking IB fabric is being used productively for training; inference (per-node NVLink replicas) needs far less of it.
- Fine-tuning (LoRA on 70B: 25-28 min on one 8-GPU node) is cheap and can be run in parallel on many nodes; per-GPU inference is ~4.4k tok/s (70B) and ~7.4k tok/s (Mixtral) in benchmarks.
- Storage and power are sized accordingly: 405B checkpoints (6.5 TB) need ~22-108 GB/s write vs RA 2-SU write ~14/40/124 GB/s (Good/Better/Best, DERIVED); DGX load ~643 kW, ~370 MWh per 30-day run at 80%.
