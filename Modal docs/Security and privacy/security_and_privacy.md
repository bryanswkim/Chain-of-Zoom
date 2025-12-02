# Security and privacy at Modal

The document outlines Modal's security and privacy commitments.

## Application security (AppSec)

AppSec is the practice of building software that is secure by design, secured
during development, secured with testing and review, and deployed securely.

- We build our software using memory-safe programming languages, including Rust
  (for our worker runtime and storage infrastructure) and Python (for our API
  servers and Modal client).
- Software dependencies are audited by Github's Dependabot.
- We make decisions that minimize our attack surface. Most interactions with
  Modal are well-described in a gRPC API, and occur through
  [`modal`](https://pypi.org/project/modal), our open-source command-line tool
  and Python client library.
- We have automated synthetic monitoring test applications that continuously
  check for network and application isolation within our runtime.
- We use HTTPS for secure connections. Modal forces HTTPS for all services using
  TLS (SSL), including our public website and the Dashboard to ensure secure
  connections. Modal's [client library](https://pypi.org/project/modal) connects
  to Modal's servers over TLS and verify TLS certificates on each connection.
- All user data is encrypted in transit and at rest.
- All public Modal APIs use
  [TLS 1.3](https://datatracker.ietf.org/doc/html/rfc8446), the latest and
  safest version of the TLS protocol.
- Internal code reviews are performed using a modern, PR-based development
  workflow (Github), and engage external penetration testing firms to assess our
  software security.

## Corporate security (CorpSec)

CorpSec is the practice of making sure Modal employees have secure access to
Modal company infrastructure, and also that exposed channels to Modal are
secured. CorpSec controls are the primary concern of standards such as SOC2.

- Access to our services and applications is gated on a SSO Identity Provider
  (IdP).
- We mandate phishing-resistant multi-factor authentication (MFA) in all
  enrolled IdP accounts.
- We regularly audit access to internal systems.
- Employee laptops are protected by full disk encryption using FileVault2, and
  managed by Secureframe MDM.

## Network and infrastructure security (InfraSec)

InfraSec is the practice of ensuring a hardened, minimal attack surface for
components we deploy on our network.

- Modal uses logging and metrics observability providers, including Datadog and
  Sentry.io.
- Compute jobs at Modal are containerized and virtualized using
  [gVisor](https://github.com/google/gvisor), the sandboxing technology
  developed at Google and used in their _Google Cloud Run_ and _Google
  Kubernetes Engine_ cloud services.
- We conduct annual business continuity and security incident exercises.
<!-- TODO: we don't yet encrypt network file system data. "Customer information on databases and volumes at Modal is encrypted with the Linux LUKS block storage encryption secrets." -->

## Vulnerability remediation

Security vulnerabilities directly affecting Modal's systems and services will be
patched or otherwise remediated within a timeframe appropriate for the severity
of the vulnerability, subject to the public availability of a patch or other
remediation mechanisms.

If there is a CVSS severity rating accompanying a vulnerability disclosure, we
rely on that as a starting point, but may upgrade or downgrade the severity
using our best judgement.

### Severity timeframes

- **Critical:** 24 hours
- **High:** 1 week
- **Medium:** 1 month
- **Low:** 3 months
- **Informational:** 3 months or longer

## Shared responsibility model

Modal prioritizes the integrity, security, and availability of customer data. Under our shared responsibility model, customers also have certain responsibilities regarding data backup, recovery, and availability.

1. **Data backup**: Customers are responsible for maintaining backups of their data. Performing daily backups is recommended. Customers must routinely verify the integrity of their backups.
2. **Data recovery**: Customers should maintain a comprehensive data recovery plan that includes detailed procedures for data restoration in the event of data loss, corruption, or system failure. Customers must routinely test their recovery process.
3. **Availability**: While Modal is committed to high service availability, customers must implement contingency measures to maintain business continuity during service interruptions. Customers are also responsible for the reliability of their own IT infrastructure.
4. **Security measures**: Customers must implement appropriate security measures, such as encryption and access controls, to protect their data throughout the backup, storage, and recovery processes. These processes must comply with all relevant laws and regulations.

## SOC 2

We have successfully completed a [System and Organization Controls (SOC) 2 Type 2
audit](/blog/soc2type2). Go to our [Security Portal](https://trust.modal.com) to request access to the report.

## HIPAA

HIPAA, which stands for the Health Insurance Portability and Accountability Act, establishes a set of standards that protect health information, including individuals’ medical records and other individually identifiable health information. HIPAA guidelines apply to both covered entities and business associates—of which Modal is the latter if you are processing PHI on Modal.

Modal's services can be used in a HIPAA compliant manner. It is important to note that unlike other security standards, there is no officially recognized certification process for HIPAA compliance. Instead, we demonstrate our compliance with regulations such as HIPAA via the practices outlined in this doc, our technical and operational security measures, and through official audits for standards compliance such as SOC 2 certification.

To use Modal services for HIPAA-compliant workloads, a Business Associate Agreement (BAA) should be established with us prior to submission of any PHI. This is available on our Enterprise plan. Contact us at security@modal.com to get started. At the moment, [Volumes v1](https://modal.com/docs/guide/volumes), [Images](https://modal.com/docs/guide/images) (persistent storage), [memory snapshots](https://modal.com/docs/guide/memory-snapshot), and user code are out of scope of the commitments within our BAA, so PHI should not be used in those areas of the product.

[Volumes v2](https://modal.com/docs/guide/volumes#volumes-v2) are HIPAA compliant.

## PCI

_Payment Card Industry Data Security Standard_ (PCI) is a standard that defines
the security and privacy requirements for payment card processing.

Modal uses [Stripe](https://stripe.com) to securely process transactions and
trusts their commitment to best-in-class security. We do not store personal
credit card information for any of our customers. Stripe is certified as "PCI
Service Provider Level 1", which is the highest level of certification in the
payments industry.

## Bug bounty program

Keeping user data secure is a top priority at Modal. We welcome contributions
from the security community to identify vulnerabilities in our product and
disclose them to us in a responsible manner. We offer rewards ranging from $100
to $1000+ depending on the severity of the issue discovered. To participate,
please send a report of the vulnerability to security@modal.com.

## Data privacy

Modal will never access or use:

- your source code.
- the inputs (function arguments) or outputs (function return values) to your Modal Functions.
- any data you store in Modal, such as in Images or Volumes.

Inputs (function arguments) and outputs (function return values) are deleted from our system after a max TTL of 7 days.

App logs and metadata are stored on Modal. Modal will not access this data
unless permission is granted by the user to help with troubleshooting.

## Questions?

[Email us!](mailto:security@modal.com)
