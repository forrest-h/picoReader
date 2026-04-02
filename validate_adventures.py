#!/usr/bin/env python3
"""Validate .adv adventure files for the picoReader adventure engine."""
import sys
import os
import re

def validate(filepath):
    errors = []
    warnings = []
    rooms = {}       # room_id -> line_number
    choices = []     # (line_num, room_id, text, target, need, pickup, use, setf)
    items_defined = {}  # item_id -> room_id
    flags_set = set()
    flags_checked = set()  # flags used in @IF or @NEED
    items_in_rooms = {}    # room_id -> count of @ITEM
    choices_in_rooms = {}  # room_id -> count of @CHOICE
    score_rooms = set()
    gameover_rooms = set()
    win_rooms = set()
    current_room = None
    title = None
    start = None

    with open(filepath, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped.startswith('@TITLE '):
            title = stripped[7:]
        elif stripped.startswith('@START '):
            start = stripped[7:]
        elif stripped.startswith('@ROOM '):
            current_room = stripped[6:]
            if current_room in rooms:
                errors.append(f"L{i}: Duplicate room '{current_room}' (first at L{rooms[current_room]})")
            rooms[current_room] = i
            items_in_rooms[current_room] = 0
            choices_in_rooms[current_room] = 0
        elif stripped.startswith('@CHOICE '):
            if current_room:
                choices_in_rooms[current_room] = choices_in_rooms.get(current_room, 0) + 1
            raw = stripped[8:]
            # Parse choice
            m = re.match(r'"([^"]*)"', raw)
            if not m:
                errors.append(f"L{i}: Malformed @CHOICE: {stripped}")
                continue
            text = m.group(1)
            if len(text) > 23:
                errors.append(f"L{i}: Choice text too long ({len(text)} chars, max 23): \"{text}\"")
            rest = raw[m.end():].strip()
            arrow = rest.find('->')
            if arrow < 0:
                errors.append(f"L{i}: @CHOICE missing '->': {stripped}")
                continue
            parts = rest[arrow+2:].strip().split()
            target = parts[0] if parts else ''
            # Count @NEED, @SET, @USE, @PICKUP
            need_count = sum(1 for p in parts if p == '@NEED')
            set_count = sum(1 for p in parts if p == '@SET')
            use_count = sum(1 for p in parts if p == '@USE')
            pickup_count = sum(1 for p in parts if p == '@PICKUP')
            if need_count > 1:
                errors.append(f"L{i}: Multiple @NEED ({need_count}) on one choice - only last is used!")
            if set_count > 1:
                errors.append(f"L{i}: Multiple @SET ({set_count}) on one choice - only last is used!")
            if use_count > 1:
                errors.append(f"L{i}: Multiple @USE ({use_count}) on one choice")
            if pickup_count > 1:
                errors.append(f"L{i}: Multiple @PICKUP ({pickup_count}) on one choice")
            # Track needs/sets
            j = 1
            need_val = None
            while j < len(parts):
                if parts[j] == '@NEED' and j+1 < len(parts):
                    need_val = parts[j+1]
                    nv = need_val.lstrip('!')
                    flags_checked.add(nv)
                    j += 2
                elif parts[j] == '@SET' and j+1 < len(parts):
                    flags_set.add(parts[j+1])
                    j += 2
                else:
                    j += 1
            choices.append((i, current_room, text, target))
        elif stripped.startswith('@ITEM '):
            if current_room:
                items_in_rooms[current_room] = items_in_rooms.get(current_room, 0) + 1
            p = stripped[6:].split('"')
            if len(p) >= 2:
                item_id = p[0].strip()
                items_defined[item_id] = current_room
        elif stripped.startswith('@IF '):
            flag = stripped[4:].lstrip('!')
            flags_checked.add(flag)
        elif stripped.startswith('@ON_ENTER @SET '):
            flags_set.add(stripped[15:])
        elif stripped.startswith('@SCORE '):
            if current_room:
                score_rooms.add(current_room)
        elif stripped.startswith('@GAMEOVER '):
            if current_room:
                gameover_rooms.add(current_room)
        elif stripped.startswith('@WIN '):
            if current_room:
                win_rooms.add(current_room)

    # Validate metadata
    if not title:
        errors.append("Missing @TITLE")
    if not start:
        errors.append("Missing @START")
    elif start not in rooms:
        errors.append(f"@START '{start}' is not a defined room")

    # Validate choice targets
    for line_num, room_id, text, target in choices:
        if target not in rooms:
            errors.append(f"L{line_num}: Choice in '{room_id}' targets non-existent room '{target}'")

    # Validate choice + item counts per room
    # Account for mutually exclusive @NEED conditions (e.g., @NEED X and @NEED !X)
    for room_id in rooms:
        total = items_in_rooms.get(room_id, 0) + choices_in_rooms.get(room_id, 0)
        if total > 4:
            # Check for mutually exclusive needs that reduce visible count
            room_needs = []
            for line_num, rid, text, target in choices:
                if rid != room_id:
                    continue
                # Re-parse to get need value
                raw_line = lines[line_num - 1].strip()[8:]
                m2 = re.match(r'"[^"]*"', raw_line)
                if not m2:
                    continue
                rest2 = raw_line[m2.end():].strip()
                arrow2 = rest2.find('->')
                if arrow2 < 0:
                    continue
                parts2 = rest2[arrow2+2:].strip().split()
                for k in range(1, len(parts2)):
                    if parts2[k] == '@NEED' and k+1 < len(parts2):
                        room_needs.append(parts2[k+1])
            # Count mutually exclusive pairs (X and !X)
            exclusive_pairs = 0
            pos_needs = [n for n in room_needs if not n.startswith('!')]
            neg_needs = [n[1:] for n in room_needs if n.startswith('!')]
            for n in pos_needs:
                if n in neg_needs:
                    exclusive_pairs += 1
            effective_max = total - exclusive_pairs
            if effective_max > 4:
                errors.append(f"Room '{room_id}': {total} visible choices ({items_in_rooms.get(room_id,0)} items + {choices_in_rooms.get(room_id,0)} choices, {exclusive_pairs} exclusive pairs), max 4")

    # Check for dead-end rooms (no choices, no gameover, no win)
    for room_id in rooms:
        if room_id not in gameover_rooms and room_id not in win_rooms:
            if choices_in_rooms.get(room_id, 0) == 0 and items_in_rooms.get(room_id, 0) == 0:
                errors.append(f"Room '{room_id}' is a dead end (no choices, no items, no end state)")

    # Warn about flags checked but never set
    for flag in flags_checked:
        if flag not in flags_set and flag not in items_defined:
            warnings.append(f"Flag/item '{flag}' checked but never @SET or defined as @ITEM")

    # Warn about score rooms that have return paths (potential score exploit)
    score_targets = set()
    for _, _, _, target in choices:
        if target in score_rooms:
            score_targets.add(target)
    for room_id in score_rooms:
        incoming = sum(1 for _, _, _, t in choices if t == room_id)
        if incoming > 1:
            warnings.append(f"Room '{room_id}' has @SCORE and {incoming} incoming paths (potential score exploit)")

    return title, len(rooms), len(choices), len(gameover_rooms), len(win_rooms), errors, warnings


def main():
    adv_dir = os.path.join(os.path.dirname(__file__), 'adventures')
    files = sorted(f for f in os.listdir(adv_dir) if f.endswith('.adv'))
    total_errors = 0

    for f in files:
        path = os.path.join(adv_dir, f)
        title, room_count, choice_count, go_count, win_count, errors, warnings = validate(path)
        status = "PASS" if not errors else "FAIL"
        print(f"\n{'='*50}")
        print(f"{status}: {f}")
        print(f"  Title: {title}")
        print(f"  Rooms: {room_count}, Choices: {choice_count}")
        print(f"  Game Overs: {go_count}, Win States: {win_count}")
        if errors:
            print(f"  ERRORS ({len(errors)}):")
            for e in errors:
                print(f"    - {e}")
            total_errors += len(errors)
        if warnings:
            print(f"  WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"    - {w}")

    print(f"\n{'='*50}")
    print(f"Total files: {len(files)}, Total errors: {total_errors}")
    return 1 if total_errors else 0


if __name__ == '__main__':
    sys.exit(main())
