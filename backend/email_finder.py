"""
Email Finder Module
Generates email patterns and finds the best valid emails
"""
from typing import List, Dict, Optional
from email_verifier import EmailVerifier


class EmailFinder:
    """Generate and verify email patterns"""
    
    def __init__(self):
        self.verifier = EmailVerifier()
    
    def generate_patterns(self, first_name: str, last_name: str, domain: str) -> List[str]:
        """
        Generate common email patterns
        Returns list of possible email addresses
        """
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        domain_lower = domain.lower().strip().rstrip('@')
        
        if not first or not last or not domain_lower:
            return []
        
        patterns = set()
        
        def add(pattern: str):
            if pattern and "@" in pattern:
                patterns.add(pattern)
        
        # Base tokens
        base = [
            f"{first}.{last}",
            f"{first}{last}",
            f"{first}_{last}",
            f"{first}-{last}",
            f"{first}",
            f"{last}.{first}",
            f"{last}{first}",
            f"{first[0]}.{last}",
            f"{first}.{last[0]}",
            f"{first[0]}{last}",
            f"{first}{last[0]}",
            f"{first[0]}{last[0]}",
            f"{first}.{last[0]}.{last}",
            f"{last}.{first[0]}",
            f"{first[0]}.{last[0]}.{last}",
        ]
        
        numeric_suffixes = ["1", "12", "123", "01", "001"]
        separators = ["", ".", "_", "-"]
        
        # Add base patterns
        for token in base:
            add(f"{token}@{domain_lower}")
        
        # Add numeric variants (e.g., first.last1, firstlast123)
        for token in base:
            for suffix in numeric_suffixes:
                add(f"{token}{suffix}@{domain_lower}")
        
        # Add split numeric combos (first1.last / f_last01, etc.)
        for sep in separators:
            add(f"{first}{sep}{last}1@{domain_lower}")
            add(f"{first}{sep}{last}99@{domain_lower}")
            add(f"{first[0]}{sep}{last}1@{domain_lower}")
            add(f"{first}{sep}{last}{first[0]}@{domain_lower}")
            add(f"{first}{sep}{last}{last[0]}@{domain_lower}")
        
        # Add reversed and initials with numbers
        add(f"{last}{first}1@{domain_lower}")
        add(f"{last}{first}123@{domain_lower}")
        add(f"{last}.{first}01@{domain_lower}")
        add(f"{first[0]}{last}{last[0]}@{domain_lower}")
        add(f"{first[0]}{last}{first[-1]}@{domain_lower}")
        add(f"{first}{last[0]}{last[-1]}@{domain_lower}")
        add(f"{first[0]}{last}{numeric_suffixes[0]}@{domain_lower}")
        
        # Catch-all pattern for first initial + middle initial + last if names long
        if len(first) > 1 and len(last) > 1:
            add(f"{first[0]}{first[1]}{last}@{domain_lower}")
            add(f"{first}{last[:2]}@{domain_lower}")
            add(f"{first[:2]}{last}@{domain_lower}")
        
        # Remove duplicates and empty patterns
        unique_patterns = list(patterns)
        
        return unique_patterns
    
    def find_best_emails(self, first_name: str, last_name: str, domain: str, 
                        max_results: int = 2, max_patterns: int = 8) -> List[Dict]:
        """
        Generate patterns, verify them, and return best matches
        Optimized to check only top patterns first
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Generate patterns
        patterns = self.generate_patterns(first_name, last_name, domain)
        logger.info(f"Generated {len(patterns)} email patterns")
        
        if not patterns:
            return []
        
        # Prioritize common patterns (check these first)
        priority_patterns = [
            f"{first_name.lower()}.{last_name.lower()}@{domain.lower()}",
            f"{first_name.lower()}{last_name.lower()}@{domain.lower()}",
            f"{first_name.lower()}@{domain.lower()}",
            f"{first_name[0].lower()}.{last_name.lower()}@{domain.lower()}",
            f"{first_name[0].lower()}{last_name.lower()}@{domain.lower()}"
        ]
        
        # Reorder patterns: priority first, then rest
        ordered_patterns = []
        seen = set()
        for p in priority_patterns:
            if p in patterns and p not in seen:
                ordered_patterns.append(p)
                seen.add(p)
        for p in patterns:
            if p not in seen:
                ordered_patterns.append(p)
        
        # Limit to configurable number of patterns to avoid timeouts
        max_patterns = max(1, min(max_patterns, len(ordered_patterns)))
        patterns_to_check = ordered_patterns[:max_patterns]
        logger.info(f"Checking {len(patterns_to_check)} patterns (limit set to {max_patterns})")
        
        # Verify each pattern
        results = []
        for i, email in enumerate(patterns_to_check):
            logger.info(f"Checking pattern {i+1}/{len(patterns_to_check)}: {email}")
            try:
                verification = self.verifier.verify_email(email)
                
                # Include valid, catch-all, or likely_valid emails
                if verification["status"] in ["valid", "catch-all", "likely_valid"]:
                    results.append({
                        "email": email,
                        "status": verification["status"],
                        "confidence": verification["confidence"],
                        "reason": verification["reason"]
                    })
                    logger.info(f"Found valid email: {email} (confidence: {verification['confidence']})")
                    
                    # If we found a high-confidence result, we can stop early
                    if verification["confidence"] >= 0.8 and len(results) >= max_results:
                        logger.info("Found high-confidence result, stopping early")
                        break
            except Exception as e:
                logger.warning(f"Error verifying {email}: {str(e)}")
                continue
        
        # Sort by confidence (descending)
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        logger.info(f"Returning {len(results[:max_results])} results")
        # Return top results
        return results[:max_results]
    
    def find_best_email(self, first_name: str, last_name: str, domain: str) -> Optional[Dict]:
        """
        Find single best email
        """
        results = self.find_best_emails(first_name, last_name, domain, max_results=1)
        return results[0] if results else None

