-- Normalization Functions for Fuzzy Matching
-- These functions help compensate for ClickHouse's lack of native full-text search

-- Email normalization: lowercase + trim
-- Usage: email_normalize('John.Doe@EXAMPLE.COM') -> 'john.doe@example.com'
CREATE FUNCTION IF NOT EXISTS email_normalize AS (email) -> lowerUTF8(trim(email));

-- Phone normalization: remove all non-digits
-- Usage: phone_normalize('+33 6 12 34 56 78') -> '33612345678'
CREATE FUNCTION IF NOT EXISTS phone_normalize AS (phone) -> replaceRegexpAll(phone, '[^0-9]', '');

-- Name soundex for phonetic matching
-- Usage: name_soundex('John') = name_soundex('Jon')
CREATE FUNCTION IF NOT EXISTS name_soundex AS (name) -> soundex(lowerUTF8(trim(name)));

-- Remove accents from text (UTF-8 normalization)
-- Handles French, Spanish, Portuguese, etc.
CREATE FUNCTION IF NOT EXISTS remove_accents AS (text) ->
    replaceRegexpAll(
        replaceRegexpAll(
            replaceRegexpAll(
                replaceRegexpAll(
                    replaceRegexpAll(
                        replaceRegexpAll(
                            replaceRegexpAll(
                                replaceRegexpAll(text,
                                    '[àáâãäåāăą]', 'a'),
                                '[èéêëēĕėęě]', 'e'),
                            '[ìíîïĩīĭ]', 'i'),
                        '[òóôõöøōŏő]', 'o'),
                    '[ùúûüũūŭů]', 'u'),
                '[ýÿŷ]', 'y'),
            '[ñń]', 'n'),
        '[çćĉċč]', 'c'
    );

-- Name normalization: lowercase + trim + remove accents
-- Usage: name_normalize('José-François') -> 'jose-francois'
CREATE FUNCTION IF NOT EXISTS name_normalize AS (name) ->
    remove_accents(lowerUTF8(trim(name)));

-- String similarity using ngramDistance (lower = more similar, 0 = identical)
-- Usage: fuzzy_match('john', 'jhon') -> 0.2 (similar)
--        fuzzy_match('john', 'mary') -> 1.0 (different)
-- This is a convenience wrapper around ngramDistance
CREATE FUNCTION IF NOT EXISTS fuzzy_match AS (str1, str2) ->
    ngramDistance(lowerUTF8(str1), lowerUTF8(str2));

-- Check if fuzzy match is within threshold (default: 0.3)
-- Usage: is_fuzzy_match('john', 'jhon', 0.3) -> 1 (true)
CREATE FUNCTION IF NOT EXISTS is_fuzzy_match AS (str1, str2, threshold) ->
    if(ngramDistance(lowerUTF8(str1), lowerUTF8(str2)) <= threshold, 1, 0);
