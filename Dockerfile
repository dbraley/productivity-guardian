FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update package list and install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    sudo \
    xdotool \
    curl \
    nano \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install psutil

# Create a test user with sudo privileges
RUN useradd -m -s /bin/bash testuser && \
    echo "testuser:testpass" | chpasswd && \
    usermod -aG sudo testuser && \
    echo "testuser ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Set working directory
WORKDIR /home/testuser/productivity_guardian

# Copy the script files
COPY productivity_guardian.py .
COPY test_runner.py .
COPY docker_test.sh .

# Make scripts executable
RUN chmod +x productivity_guardian.py docker_test.sh

# Change ownership to testuser
RUN chown -R testuser:testuser /home/testuser

# Switch to test user
USER testuser

# Set environment variables
ENV HOME=/home/testuser
ENV USER=testuser

CMD ["/bin/bash"]
