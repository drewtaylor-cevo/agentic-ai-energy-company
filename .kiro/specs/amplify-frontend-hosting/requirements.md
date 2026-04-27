# Requirements Document

## Introduction

This document defines the requirements for deploying the Customer Tariff & Billing Optimisation Agent demo UI to AWS Amplify Hosting via a new CDK stack (`CustomerTariffFrontend`). The feature replaces the current `vite preview` localhost approach with a stable, shareable HTTPS URL while preserving all existing UI behaviour including the `?narrative=off` kill switch and version indicator.

## Glossary

- **Frontend_Stack**: The new CDK stack (`CustomerTariffFrontend`) that provisions Amplify Hosting resources independently of the existing 3 stacks.
- **Amplify_Construct**: The CDK L3 construct (`AmplifyHostingConstruct`) that encapsulates Amplify App, Branch, and S3 asset deployment resources.
- **CDK_Entry_Point**: The `app.py` file that registers all CDK stacks with the CDK App.
- **Build_Output**: The `ui/dist` directory produced by `npm run build` or `npm run build:mock`, containing the static Vite production bundle.
- **SPA_Redirect_Rule**: The Amplify custom rule that rewrites all non-file URL paths to `index.html` with HTTP 200, enabling client-side routing.
- **Security_Headers**: HTTP response headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy) applied to all responses from the Amplify app.
- **Asset_Deployment**: The pattern where a pre-built local directory is packaged as an S3 asset and deployed to Amplify Hosting without a Git source code provider.

## Requirements

### Requirement 1: CDK Stack Provisioning

**User Story:** As a developer, I want a new independent CDK stack that provisions Amplify Hosting resources, so that I can deploy the frontend without affecting the existing backend infrastructure.

#### Acceptance Criteria

1. WHEN `cdk deploy CustomerTariffFrontend` is executed, THE Frontend_Stack SHALL create an Amplify Hosting app with platform set to WEB (static-only, no SSR)
2. WHEN `cdk deploy CustomerTariffFrontend` is executed, THE Frontend_Stack SHALL create a branch named "main" with the Build_Output deployed as an S3 asset
3. THE Frontend_Stack SHALL have no dependencies on the CustomerTariff, CustomerTariffAgent, or CustomerTariffApi stacks
4. WHEN the Frontend_Stack deployment completes, THE Frontend_Stack SHALL export `AmplifyAppUrl` and `AmplifyAppId` as CloudFormation outputs
5. THE CDK_Entry_Point SHALL register the Frontend_Stack with `env=cdk.Environment(region="us-east-1")`

### Requirement 2: SPA Routing

**User Story:** As a presenter, I want deep-links and query parameters to work correctly on the hosted site, so that the `?narrative=off` kill switch and any direct URL entry function as expected.

#### Acceptance Criteria

1. THE Amplify_Construct SHALL configure the SPA_Redirect_Rule on the Amplify app
2. WHEN a browser requests a URL path that does not match a static file, THE Amplify app SHALL return `index.html` with HTTP 200
3. WHEN a browser requests a URL with the `?narrative=off` query parameter, THE Amplify app SHALL serve `index.html` and allow the React app to read the query parameter client-side

### Requirement 3: Security Headers

**User Story:** As a security-conscious developer, I want appropriate security headers on all responses from the hosted frontend, so that the demo site follows security best practices.

#### Acceptance Criteria

1. THE Amplify_Construct SHALL apply Security_Headers to all responses matching the pattern `**/*`
2. THE Security_Headers SHALL include `X-Content-Type-Options` set to `nosniff`
3. THE Security_Headers SHALL include `X-Frame-Options` set to `DENY`
4. THE Security_Headers SHALL include `Referrer-Policy` set to `strict-origin-when-cross-origin`

### Requirement 4: Asset-Based Deployment

**User Story:** As a developer, I want to deploy pre-built static files to Amplify without configuring a Git provider, so that the deployment model remains simple and supports both live-API and mock-mode builds.

#### Acceptance Criteria

1. THE Amplify_Construct SHALL package the directory at `asset_path` as an S3 asset for deployment
2. WHEN the Build_Output is produced with `VITE_API_URL` set to the live API endpoint, THE deployed JS bundles SHALL contain the literal API Gateway URL string
3. WHEN the Build_Output is produced with `VITE_API_URL` set to an empty string (mock mode), THE deployed JS bundles SHALL NOT contain any `execute-api` URL
4. THE Amplify app SHALL serve content byte-identical to the Build_Output with no server-side transformation

### Requirement 5: Stack Independence and Lifecycle

**User Story:** As a developer, I want the frontend stack to be fully independent, so that I can deploy, update, or destroy it without impacting the backend stacks.

#### Acceptance Criteria

1. WHEN `cdk deploy CustomerTariffFrontend` is executed without the other 3 stacks deployed, THE deployment SHALL succeed
2. WHEN `cdk destroy CustomerTariffFrontend` is executed, THE other 3 stacks SHALL remain unaffected
3. WHEN `cdk deploy CustomerTariffFrontend` is executed twice with the same Build_Output, THE second deployment SHALL result in no CloudFormation changes (idempotent redeployment)

### Requirement 6: HTTPS and CDN Delivery

**User Story:** As a presenter or reviewer, I want the demo accessible via a stable HTTPS URL, so that I can share it without requiring local setup or VPN access.

#### Acceptance Criteria

1. THE Amplify app SHALL serve all content exclusively over HTTPS
2. WHEN the deployment completes, THE Frontend_Stack SHALL output a URL in the format `https://main.<app-id>.amplifyapp.com`
3. THE Amplify app SHALL leverage CloudFront CDN for edge caching of static assets with content-hashed filenames

### Requirement 7: Build Output Validation

**User Story:** As a developer, I want clear feedback when the build output is missing or invalid, so that I do not accidentally deploy a broken frontend.

#### Acceptance Criteria

1. IF the `ui/dist` directory does not exist at synth time, THEN THE CDK synth SHALL fail with an error indicating the asset path cannot be found
2. IF the Build_Output does not contain `index.html`, THEN THE Asset_Deployment SHALL fail during CDK synth

### Requirement 8: Version Indicator Preservation

**User Story:** As a presenter, I want the version indicator (`v2.0 · <sha>`) to render correctly on the Amplify-hosted site, so that I can verify the correct build is deployed.

#### Acceptance Criteria

1. WHEN the Build_Output is produced from the `demo-v2.0` tag, THE deployed site SHALL display the version indicator with the correct git SHA in the bottom-right corner
2. THE Amplify deployment SHALL NOT modify or strip the `__GIT_SHA__` value baked into the JS bundle at Vite build time

### Requirement 9: CORS Compatibility

**User Story:** As a presenter, I want the Amplify-hosted frontend to call the existing API Gateway without CORS errors, so that the demo works identically to the localhost version.

#### Acceptance Criteria

1. WHEN the browser on the Amplify domain sends a request to the API Gateway endpoint, THE API Gateway SHALL accept the request without CORS errors (existing `allow_origins=["*"]` configuration)
2. THE Frontend_Stack SHALL NOT require any changes to the existing API Gateway CORS configuration
