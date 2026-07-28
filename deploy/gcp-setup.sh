#!/usr/bin/env bash
# 일회성 GCP 인프라 설정 스크립트. CI가 실행하는 게 아니라 사람이 한 번 손으로 돌리는 용도.
# 실행 전 확인: gcloud config get-value project 가 pico-503205 인지 확인할 것.
set -euo pipefail

PROJECT=pico-503205
REGION=asia-northeast3
ZONE=asia-northeast3-c
OLD_GROUP_ZONE=asia-northeast3-a
DEPLOY_SA="github-deployer@${PROJECT}.iam.gserviceaccount.com"
GITHUB_REPOS=("seoyunch/PICO-BE" "seoyunch/PICO-FE")

# 1. 필요한 API 활성화
gcloud services enable \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project="$PROJECT"

# 2. 도커 이미지 저장할 Artifact Registry 저장소
gcloud artifacts repositories create pico-be \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT"

# 3. GitHub Actions가 impersonate할 배포용 서비스 계정
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer" \
  --project="$PROJECT"

# 4. 배포용 서비스 계정 권한 부여
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/compute.osLogin"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/iap.tunnelResourceAccessor"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/compute.loadBalancerAdmin"
gcloud storage buckets add-iam-policy-binding gs://pico-fontend-bucket \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/storage.objectAdmin"

# 5. OS Login 활성화 (서비스 계정으로 SSH하려면 필요)
gcloud compute project-info add-metadata \
  --metadata enable-oslogin=TRUE \
  --project="$PROJECT"

# 6. Workload Identity Pool + Provider (GitHub Actions가 키 파일 없이 인증)
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions Pool" \
  --project="$PROJECT"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='seoyunch/PICO-BE' || assertion.repository=='seoyunch/PICO-FE'" \
  --project="$PROJECT"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")

# 7. 두 레포 각각이 배포용 서비스 계정을 impersonate할 수 있도록 허용
for REPO in "${GITHUB_REPOS[@]}"; do
  gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
    --project="$PROJECT" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${REPO}"
done

# 8. 인스턴스 그룹 zone 불일치 수정: pico-vm은 asia-northeast3-c인데
#    기존 pico-instance-group은 asia-northeast3-a에 있어서 원천적으로 넣을 수 없었음.
#    현재 0대라 안전하게 지우고 올바른 zone에 재생성.
gcloud compute instance-groups unmanaged delete pico-instance-group \
  --zone="$OLD_GROUP_ZONE" --project="$PROJECT" --quiet

gcloud compute instance-groups unmanaged create pico-instance-group \
  --zone="$ZONE" --project="$PROJECT"

gcloud compute instance-groups unmanaged set-named-ports pico-instance-group \
  --zone="$ZONE" --named-ports=backend-port:8000 --project="$PROJECT"

gcloud compute instance-groups unmanaged add-instances pico-instance-group \
  --zone="$ZONE" --instances=pico-vm --project="$PROJECT"

gcloud compute backend-services add-backend pico-backend-service \
  --global --instance-group=pico-instance-group \
  --instance-group-zone="$ZONE" --project="$PROJECT"

# 9. 헬스체크가 "/"(404 남)를 보고 있던 문제 수정
gcloud compute health-checks update http backend-health-check \
  --request-path=/api/health --project="$PROJECT"

# 10. pico-vm에 Docker 설치 (최초 1회)
gcloud compute ssh pico-vm \
  --zone="$ZONE" --project="$PROJECT" --tunnel-through-iap \
  --command="curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker \$USER && sudo gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet && mkdir -p ~/pico-be/deploy"

echo "완료. 다음 수동 작업 필요:"
echo "1. deploy/docker-compose.yml 을 pico-vm의 ~/pico-be/deploy/ 로 scp (또는 --tunnel-through-iap로 직접 SSH해서 붙여넣기)"
echo "2. 같은 위치에 .env 파일을 만들어 실제 CLOVA_API_KEY/JWT_SECRET_KEY/DATABASE_URL 등 채우기 (REDIS_URL은 docker-compose가 자동으로 오버라이드하니 안 넣어도 됨)"
echo "3. GitHub 저장소(PICO-BE, PICO-FE) 각각 Settings > Secrets and variables > Actions > Variables 에 추가:"
echo "   GCP_WIF_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "   GCP_DEPLOY_SA = ${DEPLOY_SA}"
