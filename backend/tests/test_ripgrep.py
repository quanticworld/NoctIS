"""Tests for ripgrep service"""
import pytest
from app.services.ripgrep import RipgrepService
from app.models import SearchRequest, RegexTemplate


class TestRipgrepService:
    """Test RipgrepService"""

    def test_build_pattern_name_search(self):
        """Test name search pattern building"""
        request = SearchRequest(
            template=RegexTemplate.NAME_SEARCH,
            first_name="John",
            last_name="Doe",
            search_path="/tmp",
        )
        pattern = RipgrepService.build_pattern(request)
        assert pattern == r"(John.*Doe|Doe.*John)"

    def test_build_pattern_name_search_escaping(self):
        """Test name search with special regex characters"""
        request = SearchRequest(
            template=RegexTemplate.NAME_SEARCH,
            first_name="O'Brien",
            last_name="Smith-Jones",
            search_path="/tmp",
        )
        pattern = RipgrepService.build_pattern(request)
        # Should escape special characters
        assert "\\'" in pattern or "O'Brien" in pattern
        assert "Smith-Jones" in pattern or "Smith\\-Jones" in pattern

    def test_build_pattern_email(self):
        """Test email pattern"""
        request = SearchRequest(
            template=RegexTemplate.EMAIL,
            search_path="/tmp",
        )
        pattern = RipgrepService.build_pattern(request)
        assert "@" in pattern
        assert pattern == r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    def test_build_pattern_phone_fr(self):
        """Test French phone pattern"""
        request = SearchRequest(
            template=RegexTemplate.PHONE_FR,
            search_path="/tmp",
        )
        pattern = RipgrepService.build_pattern(request)
        assert "0[1-9]" in pattern

    def test_build_pattern_ip(self):
        """Test IP address pattern"""
        request = SearchRequest(
            template=RegexTemplate.IP_ADDRESS,
            search_path="/tmp",
        )
        pattern = RipgrepService.build_pattern(request)
        assert r"\d{1,3}" in pattern

    def test_build_pattern_custom(self):
        """Test custom pattern"""
        custom_pattern = r"\d{4}-\d{4}-\d{4}-\d{4}"
        request = SearchRequest(
            template=RegexTemplate.CUSTOM,
            pattern=custom_pattern,
            search_path="/tmp",
        )
        pattern = RipgrepService.build_pattern(request)
        assert pattern == custom_pattern

    def test_build_pattern_custom_without_pattern_raises(self):
        """Test custom template without pattern raises error"""
        request = SearchRequest(
            template=RegexTemplate.CUSTOM,
            search_path="/tmp",
        )
        with pytest.raises(ValueError, match="Custom template requires pattern"):
            RipgrepService.build_pattern(request)

    def test_build_pattern_name_without_names_raises(self):
        """Test name search without names raises error"""
        request = SearchRequest(
            template=RegexTemplate.NAME_SEARCH,
            search_path="/tmp",
        )
        with pytest.raises(ValueError, match="requires first_name and last_name"):
            RipgrepService.build_pattern(request)

    def test_build_rg_command_basic(self):
        """Test basic ripgrep command building"""
        request = SearchRequest(
            template=RegexTemplate.EMAIL,
            search_path="/tmp/test",
            threads=4,
            max_filesize="50M",
        )
        pattern = RipgrepService.build_pattern(request)
        cmd = RipgrepService.build_rg_command(pattern, request)

        assert "rg" in cmd
        assert pattern in cmd
        assert "--json" in cmd
        assert "--threads=4" in cmd
        assert "--max-filesize=50M" in cmd
        assert "/tmp/test" in cmd

    def test_build_rg_command_case_insensitive(self):
        """Test case insensitive flag"""
        request = SearchRequest(
            template=RegexTemplate.EMAIL,
            search_path="/tmp",
            case_insensitive=True,
        )
        pattern = RipgrepService.build_pattern(request)
        cmd = RipgrepService.build_rg_command(pattern, request)

        assert "-i" in cmd

    def test_build_rg_command_with_file_types(self):
        """Test file type filters"""
        request = SearchRequest(
            template=RegexTemplate.EMAIL,
            search_path="/tmp",
            file_types=["txt", "log"],
            exclude_types=["pdf"],
        )
        pattern = RipgrepService.build_pattern(request)
        cmd = RipgrepService.build_rg_command(pattern, request)

        assert "--type=txt" in cmd
        assert "--type=log" in cmd
        assert "--type-not=pdf" in cmd
