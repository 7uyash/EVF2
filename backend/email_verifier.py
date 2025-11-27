"""
Email Verifier Module
Handles DNS/MX checks, SMTP handshake, deliverability assessment, and catch-all detection
"""

import dns.resolver
import smtplib
import socket
import os
import random
import string
import threading
import time
from typing import Any, Dict, List, Optional
import logging
import json
try:
    # Preferred relative import when running as a package
    from . import internet_check as internet_check_module
except Exception:
    # Fall back to top-level import for test scripts or simple runs
    import internet_check as internet_check_module


# Optional: per-domain overrides for internal/testing use.
# Example:
# DOMAIN_CONFIDENCE_OVERRIDES = {
#     "heyit.me": {"min_confidence": 0.9, "force_status": "likely_valid"},
# }
DOMAIN_CONFIDENCE_OVERRIDES: Dict[str, Dict[str, Any]] = {}


class EmailVerifier:
    """Main email verification class"""
    
    def __init__(self):
        self.timeout = 3  # seconds (reduced for faster response)
        # Domains that typically block SMTP verification
        self.smtp_blocked_domains = [
            'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
            'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.co.uk',
            'aol.com', 'icloud.com', 'me.com', 'mac.com',
            'microsoft.com', 'office365.com'
        ]
        self.cache_ttl = 3600  # seconds
        self._cache_lock = threading.Lock()
        self._mx_cache: Dict[str, Dict[str, Any]] = {}
        self._deliverability_cache: Dict[str, Dict[str, Any]] = {}
        # Optional toggles from environment (set to True by default to make checks mandatory)
        # Note: HIBP requires HIBP_API_KEY env var – if missing, HIBP will be marked as skipped.
        self.enable_internet_checks = os.getenv('ENABLE_INTERNET_CHECKS', 'true').lower() in ('1', 'true', 'yes')
        self.hibp_enabled = os.getenv('ENABLE_HIBP', 'true').lower() in ('1', 'true', 'yes')
        # Allow configuring sender domain for RCPT/MAIL FROM; default to the host's domain
        self._sender_domain = os.getenv('VERIFIER_SENDER_DOMAIN') or socket.getfqdn()

    def _get_cached(self, cache: Dict[str, Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
        with self._cache_lock:
            entry = cache.get(key)
            if not entry:
                return None
            if entry["expires_at"] > time.time():
                return entry["value"]
            cache.pop(key, None)
            return None

    def _set_cache(self, cache: Dict[str, Dict[str, Any]], key: str, value: Dict[str, Any]) -> None:
        with self._cache_lock:
            cache[key] = {"value": value, "expires_at": time.time() + self.cache_ttl}
        
    def verify_email(
        self,
        email: str,
        fast_mode: bool = True,
        confidence_mode: str = "balanced",
        internet_checks: bool = True,
    ) -> Dict:
        """
        Main verification method
        Returns comprehensive verification result with confidence score
        """
        if not email or '@' not in email:
            return {
                "email": email,
                "status": "invalid",
                "confidence": 0.0,
                "reason": "Invalid email format",
                "details": {}
            }
        
        local_part, domain = email.lower().split('@', 1)
        
        result = {
            "email": email,
            "status": "unknown",
            "confidence": 0.0,
            "reason": "",
            "details": {}
        }
        
        confidence_mode = (confidence_mode or "balanced").lower()

        # Step 1: DNS/MX Check (cached)
        mx_check = self._get_cached(self._mx_cache, domain)
        if mx_check is None:
            mx_check = self.check_mx_records(domain)
            self._set_cache(self._mx_cache, domain, mx_check)
        result["details"]["mx_check"] = mx_check
        
        if not mx_check["valid"]:
            result["status"] = "invalid"
            result["confidence"] = 0.0
            result["reason"] = "Domain has no valid MX records"
            return result
        
        # Step 2: SMTP Handshake
        smtp_result = self.smtp_handshake(email, domain, mx_check["mx_hosts"])
        result["details"]["smtp_check"] = smtp_result
        
        # Step 3: Deliverability Assessment (SPF/DKIM/DMARC)
        deliverability = self._get_cached(self._deliverability_cache, domain)
        if deliverability is None:
            deliverability = self.check_deliverability(domain)
            self._set_cache(self._deliverability_cache, domain, deliverability)
        else:
            deliverability = dict(deliverability)
        deliverability["skipped"] = False
        result["details"]["deliverability"] = deliverability
        
        # Step 4: Catch-all Detection
        if fast_mode:
            catch_all = {
                "is_catchall": False,
                "test_email": None,
                "skipped": True
            }
        else:
            catch_all = self.detect_catch_all(domain, mx_check["mx_hosts"])
            catch_all["skipped"] = False
        result["details"]["catch_all"] = catch_all

        # Step 5: Internet presence checks (Google/HIBP) — always enabled by default
        if internet_checks or self.enable_internet_checks:
            try:
                result["details"]["internet_check"] = internet_check_module.check_internet_presence(
                    email,
                    enable_hibp=self.hibp_enabled,
                )
            except Exception as e:
                result["details"]["internet_check"] = {"error": str(e)}
        
        # Calculate confidence score
        confidence = self.calculate_confidence(
            smtp_result,
            catch_all,
            mx_check,
            deliverability,
            confidence_mode=confidence_mode,
        )
        
        result["confidence"] = confidence
        
        # Determine status
        if smtp_result.get("skipped"):
            # If SMTP was skipped but we have good DNS/MX/Deliverability, mark as likely valid
            if mx_check["valid"] and (deliverability["spf"] or deliverability["dmarc"]):
                result["status"] = "likely_valid"
                result["reason"] = "Domain exists with valid MX and security records (SMTP check blocked by provider)"
                result["confidence"] = min(0.75, confidence + 0.15)  # Boost confidence
            else:
                result["status"] = "unknown"
                result["reason"] = "Could not complete full verification (SMTP blocked)"
        elif smtp_result["accepted"]:
            if catch_all["is_catchall"]:
                result["status"] = "catch-all"
                result["reason"] = "Email accepted but domain uses catch-all"
            else:
                result["status"] = "valid"
                result["reason"] = "Email verified and deliverable"
        elif smtp_result["rejected"]:
            result["status"] = "invalid"
            result["reason"] = f"Mailbox rejected: {smtp_result.get('error', 'Unknown error')}"
        else:
            # SMTP timeout but good DNS - mark as likely valid
            if mx_check["valid"] and (deliverability["spf"] or deliverability["dmarc"]):
                result["status"] = "likely_valid"
                result["reason"] = "Domain valid with security records (SMTP timeout - may be blocked)"
                result["confidence"] = min(0.70, confidence + 0.10)
            else:
                result["status"] = "unknown"
                result["reason"] = "Could not verify mailbox (server unavailable or timeout)"
        
        # Apply optional per-domain overrides (for internal/test domains)
        override = DOMAIN_CONFIDENCE_OVERRIDES.get(domain)
        if override:
            min_conf = override.get("min_confidence")
            force_status = override.get("force_status")
            if isinstance(min_conf, (int, float)):
                result["confidence"] = max(result["confidence"], float(min_conf))
            if isinstance(force_status, str):
                result["status"] = force_status

        return result
    
    def check_mx_records(self, domain: str) -> Dict:
        """Check if domain exists and has valid MX records"""
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2.0
            resolver.lifetime = 4.0
            # First check if domain exists (A record)
            try:
                resolver.resolve(domain, 'A')
            except:
                pass  # Some domains only have MX, no A record
            
            # Check MX records
            mx_records = resolver.resolve(domain, 'MX')
            mx_hosts = []
            
            for mx in mx_records:
                mx_hosts.append({
                    "priority": mx.preference,
                    "host": str(mx.exchange).rstrip('.')
                })
            
            # Sort by priority
            mx_hosts.sort(key=lambda x: x["priority"])
            
            return {
                "valid": True,
                "mx_hosts": [h["host"] for h in mx_hosts],
                "mx_details": mx_hosts
            }
            
        except dns.resolver.NXDOMAIN:
            return {
                "valid": False,
                "mx_hosts": [],
                "error": "Domain does not exist"
            }
        except dns.resolver.NoAnswer:
            # Try A record as fallback
            try:
                resolver.resolve(domain, 'A')
                return {
                    "valid": True,
                    "mx_hosts": [domain],  # Use domain itself as mail server
                    "mx_details": [{"priority": 0, "host": domain}]
                }
            except:
                return {
                    "valid": False,
                    "mx_hosts": [],
                    "error": "No MX records found"
                }
        except Exception as e:
            return {
                "valid": False,
                "mx_hosts": [],
                "error": f"DNS lookup failed: {str(e)}"
            }
    
    def smtp_handshake(self, email: str, domain: str, mx_hosts: List[str]) -> Dict:
        """
        Perform SMTP handshake to check if mailbox exists
        Returns without sending email
        """
        result = {
            "accepted": False,
            "rejected": False,
            "error": None,
            "mx_used": None,
            "skipped": False
        }
        
        # Skip SMTP for known blocked domains (they block port 25)
        domain_lower = domain.lower()
        for blocked in self.smtp_blocked_domains:
            if blocked in domain_lower or domain_lower.endswith('.' + blocked):
                result["skipped"] = True
                result["error"] = f"SMTP check skipped (domain typically blocks verification)"
                return result
        
        # Skip SMTP for transactional email services (AWS SES, SendGrid, Mailgun, etc.)
        # These services don't answer RCPT TO probes - they're designed for receiving mail, not verification
        transactional_patterns = [
            'inbound-smtp',  # AWS SES
            'amazonaws.com',
            'sendgrid.net',
            'mailgun.org',
            'mailgun.com',
            'sparkpostmail.com',
            'postmarkapp.com',
            'mandrillapp.com',
        ]
        for mx_host in mx_hosts[:2]:  # Check first 2 MX hosts
            mx_lower = mx_host.lower()
            for pattern in transactional_patterns:
                if pattern in mx_lower:
                    result["skipped"] = True
                    result["error"] = f"SMTP check skipped (transactional email service - does not support mailbox verification)"
                    return result
        
        for mx_host in mx_hosts[:2]:  # Try first 2 MX hosts only
            try:
                # Connect to SMTP server
                server = smtplib.SMTP(timeout=self.timeout)
                server.set_debuglevel(0)
                
                try:
                    server.connect(mx_host, 25)
                    
                    # HELO/EHLO
                    code, message = server.ehlo()
                    if code != 250:
                        server.helo()
                    
                    # MAIL FROM (use a test sender)
                    test_sender = f"verify@{self._sender_domain}"
                    code, message = server.mail(test_sender)
                    if code not in [250, 251]:
                        server.quit()
                        continue
                    
                    # RCPT TO (this is the key check)
                    code, message = server.rcpt(email)
                    
                    server.quit()
                    
                    # Interpret response
                    # Accept a 250 or 251 as success; treat 5xx codes as rejection
                    if code in [250, 251]:
                        result["accepted"] = True
                        result["mx_used"] = mx_host
                        return result
                    elif code in [550, 553]:
                        result["rejected"] = True
                        result["error"] = "Mailbox does not exist"
                        result["mx_used"] = mx_host
                        return result
                    elif code in [450, 451]:
                        result["error"] = "Temporarily unavailable (greylisted)"
                        result["mx_used"] = mx_host
                        # Continue to next MX
                        continue
                    elif code == 421:
                        result["error"] = "Service unavailable"
                        continue
                    elif 500 <= code < 600:
                        # Permanent failure (5xx) — treat as rejection
                        result["rejected"] = True
                        result["error"] = f"Permanent SMTP error: {code}"
                        result["mx_used"] = mx_host
                        return result
                    else:
                        result["error"] = f"Unexpected response: {code} {message}"
                        continue
                        
                except smtplib.SMTPServerDisconnected:
                    continue
                except socket.timeout:
                    result["error"] = "Connection timeout"
                    continue
                except Exception as e:
                    result["error"] = f"SMTP error: {str(e)}"
                    continue
                    
            except socket.gaierror:
                continue
            except socket.timeout:
                continue
            except Exception as e:
                result["error"] = f"Connection error: {str(e)}"
                continue
        
        # If we get here, all MX hosts failed
        if not result["error"]:
            result["error"] = "Could not connect to any MX server"
        
        return result
    
    def check_deliverability(self, domain: str) -> Dict:
        """
        Check SPF, DKIM, and DMARC records
        Returns boolean flags for each
        """
        result = {
            "spf": False,
            "dkim": False,
            "dmarc": False,
            "spf_record": None,
            "dmarc_record": None,
            "skipped": False,
        }
        
        resolver = dns.resolver.Resolver()
        resolver.timeout = 2.0
        resolver.lifetime = 4.0

        # Check SPF
        try:
            txt_records = resolver.resolve(domain, 'TXT')
            for record in txt_records:
                txt_string = b''.join(record.strings).decode('utf-8', errors='ignore')
                if txt_string.startswith('v=spf1'):
                    result["spf"] = True
                    result["spf_record"] = txt_string
        except:
            pass
        
        # Check DMARC
        try:
            dmarc_domain = f"_dmarc.{domain}"
            txt_records = resolver.resolve(dmarc_domain, 'TXT')
            for record in txt_records:
                txt_string = b''.join(record.strings).decode('utf-8', errors='ignore')
                if txt_string.startswith('v=DMARC1'):
                    result["dmarc"] = True
                    result["dmarc_record"] = txt_string
        except:
            pass
        
        # DKIM is harder to check without knowing selector
        # We'll check for common selectors
        common_selectors = ['default', 'google', 'selector1', 'selector2', 'k1', 'mail']
        for selector in common_selectors:
            try:
                dkim_domain = f"{selector}._domainkey.{domain}"
                resolver.resolve(dkim_domain, 'TXT')
                result["dkim"] = True
                break
            except:
                continue
        
        return result
    
    def detect_catch_all(self, domain: str, mx_hosts: List[str]) -> Dict:
        """
        Detect if domain uses catch-all by testing a random email
        """
        # Generate random email
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))
        test_email = f"{random_string}@{domain}"
        
        result = {
            "is_catchall": False,
            "test_email": test_email,
            "skipped": False,
        }
        
        # Try SMTP check on random email
        smtp_result = self.smtp_handshake(test_email, domain, mx_hosts)
        
        if smtp_result["accepted"]:
            result["is_catchall"] = True
        
        return result
    
    def calculate_confidence(
        self,
        smtp_result: Dict,
        catch_all: Dict,
        mx_check: Dict,
        deliverability: Dict,
        *,
        confidence_mode: str = "balanced",
    ) -> float:
        """
        Calculate confidence score based on verification results
        Weights:
        - SMTP RCPT Accepted: 0.60
        - Not Catch-all: 0.15
        - Valid MX: 0.10
        - SPF/DKIM/DMARC present: 0.15
        """
        confidence = 0.0
        
        # SMTP RCPT Accepted (0.60)
        if smtp_result["accepted"]:
            confidence += 0.60
        elif smtp_result["rejected"]:
            # Explicit rejection means we're confident it's invalid
            return 0.0
        
        # Valid MX (0.10)
        if mx_check["valid"]:
            confidence += 0.10
        
        # Not Catch-all (0.15)
        if not catch_all.get("is_catchall"):
            confidence += 0.15
        
        # SPF/DKIM/DMARC present (0.15)
        security_count = sum([
            deliverability.get("spf", False),
            deliverability.get("dkim", False),
            deliverability.get("dmarc", False)
        ])
        # Give partial credit for each security feature
        confidence += (security_count / 3) * 0.15

        # Aggressive mode provides higher confidence when SMTP is inconclusive
        if confidence_mode == "aggressive":
            domain_secure = bool(deliverability.get("spf") or deliverability.get("dmarc"))
            if not smtp_result["accepted"] and mx_check["valid"] and domain_secure:
                confidence = max(confidence, 0.65)
            if smtp_result.get("skipped") and mx_check["valid"]:
                confidence = max(confidence, 0.60)
            if not catch_all.get("is_catchall") and mx_check["valid"]:
                confidence = min(confidence + 0.1, 0.95)
        
        return round(confidence, 2)


if __name__ == '__main__':
    # Quick-run for development testing and validation
    logging.basicConfig(level=logging.INFO)
    verifier = EmailVerifier()
    test_emails = [
        'contact@projexa.ai',
        'hey@om-mishra.com',
        'contact.ommishra@gmail.com',
    ]
    for e in test_emails:
        print('\n---')
        print(f'Checking: {e}')
        res = verifier.verify_email(e, fast_mode=True, confidence_mode='balanced', internet_checks=True)
        print(json.dumps(res, indent=2))

