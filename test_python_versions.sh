#!/bin/bash
set -e

# Script to test icloudpd across multiple Python versions using Docker

SUPPORTED_VERSIONS=("3.10" "3.11" "3.12")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE_TEMPLATE="$SCRIPT_DIR/Dockerfile.test-template"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log with timestamp
log() {
    echo -e "$(date '+%H:%M:%S') $1"
}

# Function to create Dockerfile for a given Python version
create_dockerfile() {
    local python_version=$1
    local dockerfile_name="Dockerfile.test-py${python_version}"
    
    cat > "$dockerfile_name" << EOF
FROM python:${python_version}-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Create virtual environment
RUN python -m venv venv
ENV PATH="/app/venv/bin:\$PATH"

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements-pip.txt
RUN pip install . --group dev --group test

# Install additional packages for Python < 3.11 timezone support
RUN if [ "\$(python -c 'import sys; print(sys.version_info.minor < 11 and sys.version_info.major == 3)')" = "True" ]; then \\
        pip install tzdata; \\
    fi

# Run tests
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "--no-cov"]
EOF
}

# Function to test a specific Python version
test_python_version() {
    local python_version=$1
    local dockerfile_name="Dockerfile.test-py${python_version}"
    local image_name="icloudpd-test-py${python_version}"
    
    log "${YELLOW}Testing Python ${python_version}...${NC}"
    
    # Create Dockerfile
    create_dockerfile "$python_version"
    
    # Build Docker image
    log "Building Docker image for Python ${python_version}..."
    if ! docker build -f "$dockerfile_name" -t "$image_name" . --quiet; then
        log "${RED}❌ Failed to build Docker image for Python ${python_version}${NC}"
        return 1
    fi
    
    # Run tests
    log "Running tests for Python ${python_version}..."
    if docker run --rm "$image_name"; then
        log "${GREEN}✅ Python ${python_version} - All tests passed${NC}"
        # Clean up
        rm -f "$dockerfile_name"
        docker rmi "$image_name" > /dev/null 2>&1 || true
        return 0
    else
        log "${RED}❌ Python ${python_version} - Tests failed${NC}"
        # Clean up
        rm -f "$dockerfile_name"
        docker rmi "$image_name" > /dev/null 2>&1 || true
        return 1
    fi
}

# Function to run specific tests for a Python version
test_specific_module() {
    local python_version=$1
    local test_module=$2
    local dockerfile_name="Dockerfile.test-py${python_version}"
    local image_name="icloudpd-test-py${python_version}-specific"
    
    log "${YELLOW}Testing Python ${python_version} with ${test_module}...${NC}"
    
    # Create Dockerfile
    create_dockerfile "$python_version"
    
    # Build Docker image
    if ! docker build -f "$dockerfile_name" -t "$image_name" . --quiet; then
        log "${RED}❌ Failed to build Docker image for Python ${python_version}${NC}"
        rm -f "$dockerfile_name"
        return 1
    fi
    
    # Run specific tests
    if docker run --rm "$image_name" python -m pytest "tests/${test_module}" -v --tb=short --no-cov; then
        log "${GREEN}✅ Python ${python_version} - ${test_module} tests passed${NC}"
        success=0
    else
        log "${RED}❌ Python ${python_version} - ${test_module} tests failed${NC}"
        success=1
    fi
    
    # Clean up
    rm -f "$dockerfile_name"
    docker rmi "$image_name" > /dev/null 2>&1 || true
    return $success
}

# Main function
main() {
    local test_module=""
    local specific_version=""
    local failed_versions=()
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --version)
                specific_version="$2"
                shift 2
                ;;
            --module)
                test_module="$2"
                shift 2
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Test icloudpd across multiple Python versions using Docker"
                echo ""
                echo "Options:"
                echo "  --version VERSION    Test specific Python version (e.g., 3.10)"
                echo "  --module MODULE      Test specific module (e.g., test_cli.py)"
                echo "  --help, -h           Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                           # Test all supported versions"
                echo "  $0 --version 3.10            # Test only Python 3.10"
                echo "  $0 --module test_cli.py      # Test CLI module across all versions"
                echo "  $0 --version 3.11 --module test_cli.py  # Test CLI on Python 3.11"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    log "${GREEN}Starting Python version testing for icloudpd${NC}"
    
    # Determine which versions to test
    local versions_to_test=()
    if [ -n "$specific_version" ]; then
        versions_to_test=("$specific_version")
    else
        versions_to_test=("${SUPPORTED_VERSIONS[@]}")
    fi
    
    # Test each version
    for version in "${versions_to_test[@]}"; do
        if [ -n "$test_module" ]; then
            if ! test_specific_module "$version" "$test_module"; then
                failed_versions+=("$version")
            fi
        else
            if ! test_python_version "$version"; then
                failed_versions+=("$version")
            fi
        fi
    done
    
    # Summary
    echo ""
    log "${GREEN}=== Test Summary ===${NC}"
    
    if [ ${#failed_versions[@]} -eq 0 ]; then
        log "${GREEN}✅ All Python versions passed tests successfully!${NC}"
        if [ -n "$test_module" ]; then
            log "   Module tested: ${test_module}"
        fi
        log "   Versions tested: ${versions_to_test[*]}"
        exit 0
    else
        log "${RED}❌ Some Python versions failed tests:${NC}"
        for version in "${failed_versions[@]}"; do
            log "${RED}   - Python $version${NC}"
        done
        log "   Passed versions: $(printf '%s ' "${versions_to_test[@]}" | grep -v "$(printf '%s\\|' "${failed_versions[@]}" | sed 's/|$//')" | xargs)"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"