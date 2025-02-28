#!/usr/bin/env python
"""
Script to update imports from 'dataclasses' to 'schemas'
"""
import os
import re
import glob

def update_file(file_path):
    """Update imports in a file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace imports
    new_content = re.sub(
        r'from llm_quest_benchmark\.dataclasses',
        'from llm_quest_benchmark.schemas',
        content
    )
    
    # Check if changes were made
    if new_content != content:
        # Save changes
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {file_path}")
        return True
    return False

def main():
    """Update imports in all Python files"""
    # Find all Python files
    python_files = glob.glob('**/*.py', recursive=True)
    
    # Update imports
    updated_files = 0
    for file_path in python_files:
        if update_file(file_path):
            updated_files += 1
    
    print(f"Updated {updated_files} files")

if __name__ == '__main__':
    main()