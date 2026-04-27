# Implementation Plan: Amplify Frontend Hosting

## Overview

Deploy the React + Vite demo UI to AWS Amplify Hosting via a new independent CDK stack (`CustomerTariffFrontend`). This involves adding the `aws_cdk.aws_amplify_alpha` dependency, creating an `AmplifyHostingConstruct` L3 construct, a `FrontendStack`, updating `app.py` to register the new stack, and writing CDK synth tests following the existing project patterns.

## Tasks

- [x] 1. Add the `aws_cdk.aws_amplify_alpha` dependency
  - [x] 1.1 Add `aws-cdk-aws-amplify-alpha==2.250.0a0` to `requirements.in`
    - Append the new dependency line after the existing `aws-cdk.aws-bedrock-agentcore-alpha` entry
    - _Requirements: Design Dependencies table_
  - [x] 1.2 Recompile the lockfile with hash pinning
    - Run `pip-compile --generate-hashes --output-file=requirements.txt requirements.in`
    - Verify the new `aws-cdk-aws-amplify-alpha` package and its transitive dependencies appear in `requirements.txt` with `--hash` entries
    - _Requirements: Design Dependencies table (hash-pinned lockfile contract)_
  - [x] 1.3 Install the updated dependencies
    - Run `pip install -r requirements.txt` to ensure the new package is available in the local environment
    - _Requirements: Design Dependencies table_

- [x] 2. Implement the AmplifyHostingConstruct
  - [x] 2.1 Create `infrastructure/constructs/amplify_hosting.py`
    - Create the `AmplifyHostingConstruct` class extending `Construct`
    - Accept `asset_path` keyword argument (path to pre-built dist directory)
    - Package the `asset_path` directory as an `aws_s3_assets.Asset`
    - Create an `amplify.App` with `app_name="customer-tariff-ui"`, `platform=amplify.Platform.WEB`
    - Add `CustomRule.SINGLE_PAGE_APPLICATION_REDIRECT` for SPA routing
    - Add `CustomResponseHeader` for pattern `**/*` with headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
    - Add a `main` branch with the S3 asset deployment
    - Expose `app_url` property returning `https://main.<app-id>.amplifyapp.com`
    - Expose `app_id` property returning the Amplify app ID
    - Follow the existing construct pattern from `infrastructure/constructs/backend_api.py`
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.2, 3.3, 3.4, 4.1, 4.4_

- [x] 3. Implement the FrontendStack
  - [x] 3.1 Create `infrastructure/frontend_stack.py`
    - Create the `FrontendStack` class extending `Stack`
    - Instantiate `AmplifyHostingConstruct` with `asset_path="ui/dist"`
    - Export `AmplifyAppUrl` and `AmplifyAppId` as `CfnOutput` values
    - Ensure no cross-stack dependencies (no SSM reads, no imports from other stacks)
    - Follow the existing stack pattern from `infrastructure/backend_api_stack.py` and `infrastructure/foundation_stack.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 6.2_

- [x] 4. Register the FrontendStack in the CDK entry point
  - [x] 4.1 Update `app.py` to import and instantiate `FrontendStack`
    - Add `from infrastructure.frontend_stack import FrontendStack`
    - Add `FrontendStack(app, "CustomerTariffFrontend", env=cdk.Environment(region="us-east-1"), description="Amplify Hosting for the demo UI")`
    - Place the new stack after the existing `BackendApiStack` instantiation, before `app.synth()`
    - Do NOT modify any of the existing 3 stack instantiations
    - _Requirements: 1.5, 5.1, 5.2_

- [x] 5. Checkpoint - Verify CDK synth works
  - Ensure `ui/dist` exists (run `npm run build:mock --prefix ui` then `cp -r ui/dist-mock ui/dist` if needed, or `npm run build --prefix ui`)
  - Run `cdk synth CustomerTariffFrontend` to verify the new stack synthesizes without errors
  - Verify the existing 3 stacks still synth correctly with `cdk synth --all`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Write CDK synth tests for the FrontendStack
  - [x] 6.1 Create `tests/test_frontend_synth.py` with core assertion tests
    - Follow the existing `tests/test_cdk_synth.py` pattern (module-scoped fixture, Template assertions)
    - Create a `synth_template` fixture that builds a `ui/dist` temp directory with a dummy `index.html` and `assets/` subdirectory, then synthesizes `FrontendStack`
    - Test: `test_has_one_amplify_app` — verify `AWS::Amplify::App` resource count is 1
    - Test: `test_has_one_amplify_branch` — verify `AWS::Amplify::Branch` resource count is 1
    - Test: `test_amplify_app_name` — verify the app name is `customer-tariff-ui`
    - Test: `test_amplify_platform_is_web` — verify platform is `WEB`
    - Test: `test_has_amplify_app_url_output` — verify `AmplifyAppUrl` CfnOutput exists
    - Test: `test_has_amplify_app_id_output` — verify `AmplifyAppId` CfnOutput exists
    - _Requirements: 1.1, 1.2, 1.4, 6.2_
  - [x] 6.2 Write property test for stack independence (Property 2)
    - **Property 2: Stack independence (no cross-stack references)**
    - Verify the synthesized CloudFormation template contains zero `Fn::ImportValue` references
    - Verify `stack.dependencies` is an empty list
    - **Validates: Requirements 1.3, 5.1, 5.2, 9.2**
  - [x] 6.3 Write property test for security headers completeness (Property 3)
    - **Property 3: Security headers completeness**
    - Verify the Amplify App resource includes all three security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
    - Verify headers are applied to pattern `**/*`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
  - [x] 6.4 Write property test for SPA redirect rule presence (Property 4)
    - **Property 4: SPA redirect rule presence**
    - Verify the Amplify App resource includes the SPA redirect custom rule (source `/<*>`, target `/index.html`, status `200`)
    - **Validates: Requirements 2.1, 2.2, 2.3**
  - [x] 6.5 Write property test for static platform configuration (Property 5)
    - **Property 5: Static platform configuration**
    - Verify the Amplify App resource has Platform set to `WEB`
    - **Validates: Requirements 1.1, 6.1**

- [x] 7. Final checkpoint - Ensure all tests pass
  - Run `pytest` to verify all existing and new tests pass
  - Verify the existing 3 stacks are unaffected by running `cdk synth --all`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The design uses Python (CDK) throughout — all implementation is in Python
- The `aws_cdk.aws_amplify_alpha` module is experimental; pin to `2.250.0a0` to match the existing `aws-cdk-aws-bedrock-agentcore-alpha` version
- A pre-built `ui/dist` directory must exist before `cdk synth` or `cdk deploy` — the CDK stack does not build the UI
- Property tests validate correctness properties from the design document via CDK template assertions
- Actual deployment (`cdk deploy CustomerTariffFrontend`) and post-deployment smoke tests are manual steps outside this task list
