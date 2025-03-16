#!/bin/bash
set -e  # Exit on error

# Create quests directory if it doesn't exist
QUESTS_DIR="quests"
mkdir -p "$QUESTS_DIR"

# Temporary download directory
TMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TMP_DIR"

# Download repository
echo "Downloading quests from GitLab..."
wget https://gitlab.com/spacerangers/spacerangers.gitlab.io/-/archive/master/spacerangers.gitlab.io-master.zip -O "$TMP_DIR/repo.zip"

# Unzip repository
echo "Extracting files..."
unzip -q "$TMP_DIR/repo.zip" -d "$TMP_DIR"

# Copy quest files to quests directory
echo "Copying quest files to $QUESTS_DIR directory..."
cp -r "$TMP_DIR/spacerangers.gitlab.io-master/borrowed/qm/"* "$QUESTS_DIR/"

# Clean up
echo "Cleaning up temporary files..."
rm -rf "$TMP_DIR"

echo "Quest files successfully downloaded to $QUESTS_DIR directory!"
echo "Total quest files: $(find "$QUESTS_DIR" -name "*.qm" | wc -l)"