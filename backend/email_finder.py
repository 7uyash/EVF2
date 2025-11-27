"""
Email Finder Module
Generates email patterns and finds the best valid emails
"""
from typing import Dict, List, Optional, Sequence

from email_verifier import EmailVerifier

DEFAULT_PATTERN_TEMPLATES: Sequence[str] = (
    "{first}.{last}",
    "{first}_{last}",
    "{first}-{last}",
    "{first}{last}",
    "{first}{l}",
    "{f}{last}",
    "{f}.{last}",
    "{first}.{l}",
    "{last}.{first}",
    "{last}_{first}",
    "{last}{first}",
    "{f}{l}{last}",
    "{first}{last}{f}",
    "{first}{last}{l}",
    "{last}{first}{l}",
    "{f}{last}{digits2}",
    "{first}{last}{digits2}",
    "{f}{l}{digits2}",
)

NUMERIC_SUFFIXES = ["1", "12", "99", "01", "001", "123"]
SEPARATORS = ["", ".", "_", "-"]


class EmailFinder:
    """Generate and verify email patterns"""

    def __init__(self):
        self.verifier = EmailVerifier()

    def generate_patterns(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        *,
        custom_patterns: Optional[Sequence[str]] = None,
        include_defaults: bool = True,
    ) -> List[str]:
        """
        Generate email patterns from built-in templates plus optional custom patterns.
        Custom patterns support tokens:
            {first}, {last}, {f} (first initial), {l} (last initial),
            {fi}, {li}, {first3}, {last3}, {domain}
        """
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        domain_lower = domain.lower().strip().rstrip("@")

        if not first or not last or not domain_lower:
            return []

        patterns: List[str] = []
        seen = set()

        def add(pattern: str):
            if not pattern:
                return
            email = pattern if "@" in pattern else f"{pattern}@{domain_lower}"
            if email not in seen:
                patterns.append(email)
                seen.add(email)

        tokens = {
            "first": first,
            "last": last,
            "f": first[0] if first else "",
            "l": last[0] if last else "",
            "fi": first[:2],
            "li": last[:2],
            "first3": first[:3],
            "last3": last[:3],
            "domain": domain_lower,
            "digits2": "12",
        }

        if include_defaults:
            for template in DEFAULT_PATTERN_TEMPLATES:
                try:
                    add(template.format(**tokens))
                except KeyError:
                    continue

        base_tokens = [
            f"{first}.{last}",
            f"{first}{last}",
            f"{first}_{last}",
            f"{first}-{last}",
            f"{first}{last[:1]}",
            f"{first[:1]}{last}",
            f"{last}{first}",
            f"{last}.{first}",
        ]
        for token in base_tokens:
            for suffix in NUMERIC_SUFFIXES:
                add(f"{token}{suffix}")

        for sep in SEPARATORS:
            add(f"{first}{sep}{last}")
            add(f"{first[:1]}{sep}{last}")
            add(f"{first}{sep}{last[:1]}")
            add(f"{first}{sep}{last}{tokens['f']}")
            add(f"{first}{sep}{last}{tokens['l']}")

        add(f"{last}{first}1")
        add(f"{last}{first}123")
        add(f"{tokens['f']}{last}{tokens['l']}")
        add(f"{tokens['f']}{last}{first[-1] if first else ''}")
        add(f"{first}{tokens['l']}{last[-1] if last else ''}")
        add(f"{tokens['f']}{last}1")

        if len(first) > 1 and len(last) > 1:
            add(f"{tokens['f']}{first[1]}{last}")
            add(f"{first}{last[:2]}")
            add(f"{first[:2]}{last}")

        if custom_patterns:
            for template in custom_patterns:
                template = template.strip()
                if not template:
                    continue
                try:
                    add(template.format(**tokens))
                except KeyError:
                    continue

        return patterns

    def find_best_emails(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        max_results: int = 2,
        max_patterns: int = 8,
        *,
        custom_patterns: Optional[Sequence[str]] = None,
        include_defaults: bool = True,
        fast_mode: bool = True,
        confidence_mode: str = "balanced",
        internet_checks: bool = False,
    ) -> List[Dict]:
        """
        Generate patterns, verify them, and return best matches
        Optimized to check only top patterns first
        """
        import logging

        logger = logging.getLogger(__name__)

        patterns = self.generate_patterns(
            first_name,
            last_name,
            domain,
            custom_patterns=custom_patterns,
            include_defaults=include_defaults,
        )
        logger.info(f"Generated {len(patterns)} email patterns")

        if not patterns:
            return []

        priority_patterns = [
            f"{first_name.lower()}.{last_name.lower()}@{domain.lower()}",
            f"{first_name.lower()}{last_name.lower()}@{domain.lower()}",
            f"{first_name.lower()}@{domain.lower()}",
            f"{first_name[0].lower()}.{last_name.lower()}@{domain.lower()}",
            f"{first_name[0].lower()}{last_name.lower()}@{domain.lower()}",
        ]

        ordered_patterns = []
        seen = set()
        for p in priority_patterns:
            if p in patterns and p not in seen:
                ordered_patterns.append(p)
                seen.add(p)
        for p in patterns:
            if p not in seen:
                ordered_patterns.append(p)

        max_patterns = max(1, min(max_patterns, len(ordered_patterns)))
        patterns_to_check = ordered_patterns[:max_patterns]
        logger.info(f"Checking {len(patterns_to_check)} patterns (limit set to {max_patterns})")

        results = []
        for i, email in enumerate(patterns_to_check):
            logger.info(f"Checking pattern {i+1}/{len(patterns_to_check)}: {email}")
            try:
                verification = self.verifier.verify_email(
                    email,
                    fast_mode=fast_mode,
                    confidence_mode=confidence_mode,
                    internet_checks=internet_checks,
                )

                if verification["status"] in ["valid", "catch-all", "likely_valid"]:
                    results.append(
                        {
                            "email": email,
                            "status": verification["status"],
                            "confidence": verification["confidence"],
                            "reason": verification["reason"],
                        }
                    )
                    logger.info(
                        f"Found valid email: {email} (confidence: {verification['confidence']})"
                    )

                    if verification["confidence"] >= 0.8 and len(results) >= max_results:
                        logger.info("Found high-confidence result, stopping early")
                        break
            except Exception as e:
                logger.warning(f"Error verifying {email}: {str(e)}")
                continue

        results.sort(key=lambda x: x["confidence"], reverse=True)

        logger.info(f"Returning {len(results[:max_results])} results")
        return results[:max_results]

    def find_best_email(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        *,
        custom_patterns: Optional[Sequence[str]] = None,
        include_defaults: bool = True,
        fast_mode: bool = True,
        confidence_mode: str = "balanced",
        internet_checks: bool = False,
    ) -> Optional[Dict]:
        """
        Find single best email
        """
        results = self.find_best_emails(
            first_name,
            last_name,
            domain,
            max_results=1,
            custom_patterns=custom_patterns,
            include_defaults=include_defaults,
            fast_mode=fast_mode,
            confidence_mode=confidence_mode,
            internet_checks=internet_checks,
        )
        return results[0] if results else None

