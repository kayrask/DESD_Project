# Produce Quality Assessment System — Technical Report

**Bristol Regional Food Network Digital Marketplace**  
**Module: Advanced Artificial Intelligence (UFCFUR-15-3)**  
**GitHub Repository: https://github.com/kayrask/DESD_Project**

---

## 1. Problem Characteristics and Challenges

The Bristol Regional Food Network marketplace requires producers to assess the visual quality of fresh produce before listing products or fulfilling orders. Manual quality grading is labour-intensive, inconsistent across producers, and inherently subjective. An automated computer vision approach was identified as the most scalable solution, but several characteristics of this problem made implementation technically challenging.

**Class imbalance and asymmetric risk.** In a real-world harvest context, rotten produce samples are less frequent than healthy ones. A naively trained classifier could achieve high accuracy by predicting "Healthy" for almost every image, yet this would be dangerous in production — delivering rotten food to consumers represents a food safety and reputational risk far greater than a false rejection. This asymmetry required deliberate treatment in the loss function rather than relying on accuracy alone as the training signal.

**High intra-class visual variance.** The classifier must generalise across dozens of fruit and vegetable species: a healthy strawberry and a healthy courgette share the abstract property of freshness but are visually unrelated. The model cannot rely on object identity; it must learn domain-specific freshness cues such as colour uniformity, surface texture, and the presence of browning or mould patterns.

**Deployment constraints.** The system runs as a Docker-containerised web service on CPU-only infrastructure. This ruled out large architectures such as ResNet-152 or Vision Transformers, which carry gigabyte-scale memory footprints and multi-second per-image inference times. The selected architecture had to balance accuracy against a practical deployment budget.

**Interpretability for non-technical users.** Producers are small business operators, not data scientists. A confidence score alone is insufficient; the system must explain which visual dimension (colour, texture, size) drove the grade. Without this, producer trust in the tool cannot be established and the responsible-AI requirement for transparency cannot be met.

---

## 2. Candidate Approaches Considered

Three primary approaches were evaluated before selecting the final architecture.

**KMeans colour clustering (unsupervised baseline).** Pixel colours are clustered into three groups; the proportion of "green" versus "brown" cluster members estimates freshness. This approach has zero training-data dependency and was retained as a runtime fallback when no trained model file is present. Its major limitation is a complete inability to capture texture or structural features, yielding approximately 70% accuracy in informal testing — insufficient for a food safety context.

**Custom CNN from scratch.** A shallow convolutional network trained from random initialisation was considered. This was rejected for two reasons: (a) the available dataset (~29,000 images) is insufficient to train a deep network without severe overfitting without extensive regularisation and augmentation, and (b) the team lacked access to GPU infrastructure for the multi-day training runs this would require to converge reliably.

**Transfer learning on ImageNet-pretrained backbones.** This was the selected approach. Three architectures were compared: ResNet-50, EfficientNet-B0, and MobileNetV2. ResNet-50 produced a ~95 MB model checkpoint and higher peak memory usage without measurable accuracy benefit on this binary task. EfficientNet-B0 achieved comparable accuracy but its compound-scaling coefficients made hyperparameter tuning less predictable. **MobileNetV2** (Sandler et al., 2018) was selected because its inverted residual blocks and depthwise separable convolutions produce a lightweight model (~14 MB checkpoint) well-suited to CPU inference, while its pretrained features transfer effectively to the produce domain.

---

## 3. Design and Implementation

### 3.1 Architecture

The final model uses MobileNetV2 pretrained on ImageNet-1k, with its classifier replaced by a two-layer head: `Dropout(0.3) → Linear(1280, 2)`. The two output classes are Healthy (0) and Rotten (1).

Training uses a two-phase progressive fine-tuning strategy:

- **Phase 1 — Warmup** (3 epochs): The entire MobileNetV2 feature extractor is frozen. Only the classifier head is trained at a learning rate of 1×10⁻³. This stabilises the head's weights before any deeper layers are modified.
- **Phase 2 — Fine-tune** (7 epochs): The last three feature blocks (indices 16–18 of `model.features`) are unfrozen and trained jointly at 1×10⁻⁴ (10× lower). Blocks 0–15 remain frozen; they capture transferable low-level edge and texture features that generalise well across domains without adaptation.

### 3.2 Dataset

Training used the **Fruit and Vegetable Disease (Healthy vs Rotten)** dataset sourced from Kaggle. Folder names containing "Healthy" or "Fresh" were mapped to class 0; those containing "Rotten" to class 1. The full dataset (29,291 images) was split 80/20 using a fixed seed (42), yielding 23,433 training images and 5,858 validation images with guaranteed zero overlap.

### 3.3 Training Configuration

| Hyperparameter | Value |
|---|---|
| Image size | 224 × 224 |
| Batch size | 32 |
| Optimiser | Adam, weight decay 1×10⁻⁴ |
| Loss | CrossEntropyLoss, label smoothing 0.1, class weights [1.0, 2.0] |
| Scheduler | CosineAnnealingLR |
| Gradient clipping | max_norm = 1.0 |
| Early stopping | patience = 3 epochs on val_acc |

The **class-weighted loss** (Rotten weight = 2×) is the most consequential responsible-AI design decision: missed rotten produce (false negatives) carry greater food safety risk than false positive rejections, so the training signal explicitly penalises them more heavily. Label smoothing (0.1) reduces overconfidence and improves generalisation across the diverse produce categories. Gradient clipping stabilises Phase 2 fine-tuning where unfrozen backbone gradients can otherwise spike.

Training augmentations (applied only to the training split) include random horizontal and vertical flips, rotation (±20°), colour jitter (brightness, contrast, saturation), and random erasing, mimicking real-world produce photography conditions.

### 3.4 Inference Pipeline

At runtime, `ml/inference.py` maintains a module-level model cache loaded once per process, avoiding repeated disk reads on every request. Each uploaded image is preprocessed (resize to 224×224, ImageNet mean/std normalisation), passed through the model, and a softmax confidence for the Healthy class is returned.

The final quality scores blend CNN output with independent pixel-level analysis (60% CNN, 40% image scores). Three pixel-level scores are derived:

- **Color score**: proportion of fresh (green/yellow) versus rotten (brown) pixels using HSV saturation analysis.
- **Ripeness score**: surface smoothness estimated via mean Sobel edge density — lower edge density correlates with fresher, less degraded produce.
- **Size score**: centre-crop variance relative to corner variance, approximating how well the subject fills the frame.

This hybrid approach ensures graceful degradation: when CNN confidence is low, pixel scores provide a meaningful floor rather than a binary pass/fail.

### 3.5 Explainability (XAI)

Two complementary XAI mechanisms are implemented:

**Grad-CAM** (Selvaraju et al., 2017): Forward and backward hooks are registered on the final convolutional block. Gradients of the Healthy-class logit with respect to feature-map activations are globally average-pooled to produce per-channel weights. A weighted combination of the activation maps forms a coarse saliency map, upsampled to 224×224 and blended onto the original image. The result is returned as a base64-encoded PNG displayed in the quality check interface, allowing producers to see which image regions the model attended to.

**Natural-language explanation**: Each assessment produces a plain-English sentence identifying which dimension drove the grade (e.g., *"Grade C — notable discolouration detected; surface irregularities suggest over-ripeness or rot"*). This is targeted at non-technical producers who cannot interpret heatmaps.

### 3.6 System Integration

The ML stack integrates with the Django application through three layers. `app/services/quality_service.py` calls `ml/inference.py` and persists a `QualityAssessment` ORM record storing the grade, three sub-scores, model confidence, model version, and any warnings. Model re-evaluation after an admin uploads a new checkpoint is triggered via a Celery background task (`api/tasks.py`) using `subprocess.run` to invoke `ml/evaluate.py` as a child process. This subprocess isolation prevents PyTorch's memory allocator from competing with the Celery worker process — a critical stability measure on memory-constrained deployments.

---

## 4. Evaluation

The model was evaluated on the full 5,858-image held-out validation set:

| Metric | Value |
|---|---|
| Accuracy | 95.97% |
| Precision (macro) | 96.05% |
| Recall (macro) | 95.88% |
| F1-score (macro) | 95.95% |

**Confusion matrix:**

| | Predicted Healthy | Predicted Rotten |
|---|---|---|
| **Actual Healthy** | 2,603 (TN) | 156 (FP) |
| **Actual Rotten** | 80 (FN) | 3,019 (TP) |

The 80 false negatives (rotten produce classified as healthy) represent the highest-risk category. The class-weighted training objective demonstrably suppressed these: 80 FN versus 156 FP indicates the model successfully biases toward Rotten recall. The hit rate for healthy produce (correct identification) is 94.3%, confirming the model does not over-aggressively penalise producers by rejecting healthy batches.

**Limitations.** The dataset consists primarily of controlled studio photographs. Producer-submitted images may include motion blur, varied lighting, or cluttered backgrounds that reduce CNN confidence. The 60% low-confidence threshold is calibrated to surface these cases for manual review. Future work could include a test set drawn from real producer uploads to measure distribution shift and incorporate active learning to fine-tune on in-domain images.

---

## 5. Use of Generative AI

Generative AI (Claude Sonnet 3.5, Claude Sonnet 4.5) was used across four dimensions of the project:

**Code generation and scaffolding.** Training pipeline boilerplate (DataLoader configuration, checkpoint saving, transform composition) was initially generated via prompting and subsequently reviewed and modified. The Grad-CAM implementation was adapted from a prompted skeleton based on the Selvaraju et al. paper. The generated hook registration code used a deprecated PyTorch API (`register_backward_hook` instead of `register_full_backward_hook`) and required manual correction before it functioned reliably. All generated code was validated against the dataset before acceptance.

**Architectural design consultation.** The selection between MobileNetV2, EfficientNet-B0, and ResNet-50 was discussed with Claude, which surfaced the MobileNetV2 memory-footprint advantage. The asymmetric class weight design decision emerged from a prompted discussion about food safety risk framing; the final weight ratio (1.0 / 2.0) was determined empirically.

**Integration architecture.** The subprocess isolation strategy for the Celery evaluation task was suggested by Claude after diagnosing out-of-memory failures when PyTorch was imported in-process alongside concurrency=2 worker processes. This saved approximately four hours of debugging time.

**Report and documentation drafting.** Module docstrings in `train.py`, `inference.py`, and `quality_service.py` were drafted using generative AI and edited for accuracy. Portions of this report were drafted using the same tool.

**Critical assessment.** Generative AI was most valuable for scaffolding, ideation, and surfacing non-obvious architectural trade-offs. It was least reliable for specific API details (frequently citing deprecated calls) and metric interpretation (occasionally fabricating benchmark numbers). A mandatory verification pass — running the code, checking the PyTorch documentation, and validating all cited values against the actual evaluation output — was required after every generated artefact.

---

## 6. Legal, Ethical, and Professional Considerations

### 6.1 Data and Privacy

The training dataset is publicly licensed on Kaggle under a permissive licence. No personal data, producer proprietary images, or identifiable customer information are used in training. Producer-uploaded inference images are stored in `media/quality_checks/` and linked exclusively to the submitting producer's account, inaccessible to other producers or customers. The `QualityAssessment` model includes `assessed_by` (FK to User) and `assessed_at` (datetime) fields to support data subject access requests under UK GDPR.

### 6.2 Fairness, Accountability, and Trust

Several design decisions directly address FAT principles:

- **Asymmetric loss weighting** encodes an explicit ethical priority: consumer harm from rotten produce is weighted more heavily than producer inconvenience from false rejections. This is documented in code comments and disclosed to operators.
- **Producer override**: The quality grade is a decision-support tool, not an enforcer. Producers can add notes to any assessment to record disagreement. No product is blocked from listing on AI grade alone.
- **Audit trail**: Every `QualityAssessment` record stores `model_version`, enabling retrospective analysis if a food safety incident occurs and a specific model version is implicated.
- **Low-confidence warnings**: Predictions below 60% confidence surface a visible warning, preventing over-reliance on uncertain model outputs and directing producers toward manual review.
- **Grade C → discount, not removal**: Rather than hiding borderline produce, the system automatically applies a 20% discount, supporting the case study's food waste reduction objective while remaining transparent with customers about quality.

### 6.3 Professional Standards

The system is not presented as a certified food safety instrument. All interfaces describe it as an "AI-assisted quality indicator." Producers operating under the UK Food Safety Act 1990 and retained EU allergen labelling regulations retain full legal responsibility for listed produce. Allergen and organic certification fields are producer-declared and not AI-inferred, deliberately avoiding automated liability for safety-critical classifications.

---

## References

Sandler, M., Howard, A., Zhu, M., Zhmoginov, A. and Chen, L.C. (2018). MobileNetV2: Inverted Residuals and Linear Bottlenecks. *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*, pp. 4510–4520.

Selvaraju, R.R., Cogswell, M., Das, A., Vedantam, R., Parikh, D. and Batra, D. (2017). Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localisation. *Proceedings of the IEEE International Conference on Computer Vision (ICCV)*, pp. 618–626.

Howard, A.G., Zhu, M., Chen, B., Kalenichenko, D., Wang, W., Weyand, T., Andreetto, M. and Adam, H. (2017). MobileNets: Efficient Convolutional Neural Networks for Mobile Vision Applications. *arXiv preprint* arXiv:1704.04861.

Paszke, A. et al. (2019). PyTorch: An Imperative Style, High-Performance Deep Learning Library. *Advances in Neural Information Processing Systems (NeurIPS)*, 32, pp. 8024–8035.

Mishra, A. (2021). *Fruit and Vegetable Disease (Healthy vs Rotten) Dataset*. Kaggle. [online] Available at: https://www.kaggle.com/datasets/muhammad0subhan/fruit-and-vegetable-disease-healthy-vs-rotten [accessed 22 April 2026].

Information Commissioner's Office (2023). *Guide to the UK General Data Protection Regulation*. [online] Available at: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources [accessed 22 April 2026].
