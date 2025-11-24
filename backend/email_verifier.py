"""
Email Verifier Module
Handles DNS/MX checks, SMTP handshake, deliverability assessment, and catch-all detection
"""

import dns.resolver
import smtplib
import socket
import random
import string
from typing import Dict, List


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
        
    def verify_email(self, email: str) -> Dict:
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
        
        # Step 1: DNS/MX Check
        mx_check = self.check_mx_records(domain)
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
        deliverability = self.check_deliverability(domain)
        result["details"]["deliverability"] = deliverability
        
        # Step 4: Catch-all Detection
        catch_all = self.detect_catch_all(domain, mx_check["mx_hosts"])
        result["details"]["catch_all"] = catch_all
        
        # Calculate confidence score
        confidence = self.calculate_confidence(
            smtp_result,
            catch_all,
            mx_check,
            deliverability
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
        
        return result
    
    def check_mx_records(self, domain: str) -> Dict:
        """Check if domain exists and has valid MX records"""
        try:
            # First check if domain exists (A record)
            try:
                dns.resolver.resolve(domain, 'A')
            except:
                pass  # Some domains only have MX, no A record
            
            # Check MX records
            mx_records = dns.resolver.resolve(domain, 'MX')
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
                dns.resolver.resolve(domain, 'A')
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
                    test_sender = f"test@{domain}"
                    code, message = server.mail(test_sender)
                    if code not in [250, 251]:
                        server.quit()
                        continue
                    
                    # RCPT TO (this is the key check)
                    code, message = server.rcpt(email)
                    
                    server.quit()
                    
                    # Interpret response
                    if code == 250:
                        result["accepted"] = True
                        result["mx_used"] = mx_host
                        return result
                    elif code == 550:
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
            "dmarc_record": None
        }
        
        # Check SPF
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
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
            txt_records = dns.resolver.resolve(dmarc_domain, 'TXT')
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
                dns.resolver.resolve(dkim_domain, 'TXT')
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
            "test_email": test_email
        }
        
        # Try SMTP check on random email
        smtp_result = self.smtp_handshake(test_email, domain, mx_hosts)
        
        if smtp_result["accepted"]:
            result["is_catchall"] = True
        
        return result
    
    def calculate_confidence(self, smtp_result: Dict, catch_all: Dict, 
                           mx_check: Dict, deliverability: Dict) -> float:
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
        if not catch_all["is_catchall"]:
            confidence += 0.15
        
        # SPF/DKIM/DMARC present (0.15)
        security_count = sum([
            deliverability["spf"],
            deliverability["dkim"],
            deliverability["dmarc"]
        ])
        # Give partial credit for each security feature
        confidence += (security_count / 3) * 0.15
        
        return round(confidence, 2)

