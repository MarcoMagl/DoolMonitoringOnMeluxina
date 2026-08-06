#!/usr/bin/env Rscript
# ============================================================================
# Dool CSV Processing and Visualization Script
# ============================================================================
# Processes dool monitoring CSV files from a compute run directory.
# Each file (dool-N.csv) corresponds to a compute node N.
#
# Usage: ./dool-monitoring.R [run_directory]
#   run_directory: Directory containing dool-*.csv files (default: current directory)
# ============================================================================

library(tidyverse)
library(patchwork)

# --- Parameters ---
# Get directory from command line arguments, or use current working directory
args <- commandArgs(trailingOnly = TRUE)
run_dir <- if (length(args) > 0) args[1] else "."

# --- 1. Discover dool CSV files ---
csv_files <- list.files(run_dir, pattern = "^dool-\\d+\\.csv$", full.names = TRUE)

if (length(csv_files) == 0) {
  stop("No dool-*.csv files found in ", run_dir)
}

cat("Found", length(csv_files), "dool CSV file(s):\n")
cat(paste(basename(csv_files), collapse = "\n"), "\n\n")

# --- 2. Read and parse dool CSV files ---
# Dool CSV has 4 metadata rows, then a category row, then column names, then data.
read_dool <- function(filepath) {
  # Extract node number from filename (e.g., dool-0.csv -> 0)
  node <- as.integer(sub("dool-(\\d+)\\.csv$", "\\1", basename(filepath)))

  # Skip the first 4 metadata rows; row 5 is category labels, row 6 is column names
  df <- read_csv(filepath, skip = 5, show_col_types = FALSE)

  # Rename duplicate columns to avoid ambiguity (only if they exist)
  # GPU usage % columns: total, gpu0..gpu3
  # GPU memory columns: total, gpu0..gpu3 (duplicated names)
  rename_map <- list(
    gpu_usage_total = "total...26",
    gpu_usage_0     = "gpu0...27",
    gpu_usage_1     = "gpu1...28",
    gpu_usage_2     = "gpu2...29",
    gpu_usage_3     = "gpu3...30",
    gpu_mem_total   = "total...31",
    gpu_mem_0       = "gpu0...32",
    gpu_mem_1       = "gpu1...33",
    gpu_mem_2       = "gpu2...34",
    gpu_mem_3       = "gpu3...35"
  )
  
  # Only rename columns that actually exist (check old names, not new names)
  old_names <- unname(rename_map)
  existing_renames <- rename_map[old_names %in% colnames(df)]
  if (length(existing_renames) > 0) {
    df <- df |> rename(!!!existing_renames)
  }

  df |>
    mutate(node = node)
}

data_list <- csv_files |>
  set_names() |>
  map(read_dool)

# Combine all nodes into a single data frame
all_data <- data_list |>
  bind_rows()

# Convert epoch to relative time in hours (since first measurement across all nodes)
first_epoch <- min(all_data$epoch, na.rm = TRUE)
all_data <- all_data |>
  mutate(time_hours = (epoch - first_epoch) / 3600)

cat("Combined data:", nrow(all_data), "rows x", ncol(all_data), "columns\n")
cat("Nodes:", sort(unique(all_data$node)), "\n")
cat("Time range:", round(min(all_data$time_hours), 1), "to", round(max(all_data$time_hours), 1), "hours\n\n")

# --- 3. Column groups ---
# Define logical groups of columns for analysis
col_groups <- list(
  cpu    = c("usr", "sys", "idl", "wai", "stl"),
  memory = c("used", "free", "cach"),  # Removed 'avai' as it's similar to 'free'
  gpu    = c("gpu_usage_0", "gpu_usage_1", "gpu_usage_2", "gpu_usage_3"),
  disk   = c("dsk/sda:read", "dsk/sda:writ"),
  net    = c("net/ib0:recv", "net/ib0:send", "net/ib1:recv", "net/ib1:send")
)

# --- 4. Summary statistics per node ---
cat("--- Summary Statistics per Node ---\n")

for (grp_name in names(col_groups)) {
  cols <- col_groups[[grp_name]]
  available_cols <- intersect(cols, colnames(all_data))
  if (length(available_cols) == 0) next

  cat("\n[", grp_name, "]\n")
  summary_tbl <- all_data |>
    group_by(node) |>
    summarise(across(all_of(available_cols),
                     list(mean = ~mean(., na.rm = TRUE),
                          sd   = ~sd(., na.rm = TRUE)),
                     .names = "{.col}_{.fn}"),
              .groups = "drop")
  print(summary_tbl)
}

# --- 5. Visualization ---
# Helper: convert bytes to human-readable GB
bytes_to_gb <- function(x) x / (1024^3)

# Output PDF will be saved in the same directory as the CSV files
output_pdf <- file.path(run_dir, "dool_monitoring.pdf")

# --- 5a. CPU usage over time (stacked area per node) ---
cpu_data <- all_data |>
  select(node, time_hours, all_of(col_groups$cpu)) |>
  pivot_longer(cols = all_of(col_groups$cpu),
               names_to = "metric", values_to = "value")

p1 <- ggplot(cpu_data, aes(x = time_hours, y = value, fill = metric)) +
  geom_area(alpha = 0.7, position = "stack") +
  facet_wrap(~ node, ncol = 1, scales = "free_y") +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "CPU Usage Over Time",
       x = "Time (hours)", y = "CPU %", fill = "Metric") +
  theme_minimal() +
  theme(legend.position = "bottom")

# --- 5b. Memory usage over time ---
mem_data <- all_data |>
  select(node, time_hours, all_of(col_groups$memory)) |>
  mutate(across(all_of(col_groups$memory), bytes_to_gb)) |>
  pivot_longer(cols = all_of(col_groups$memory),
               names_to = "metric", values_to = "value_gb")

p2 <- ggplot(mem_data, aes(x = time_hours, y = value_gb, fill = metric)) +
  geom_area(alpha = 0.7, position = "stack") +
  facet_wrap(~ node, ncol = 1, scales = "free_y") +
  scale_fill_brewer(palette = "Set1") +
  labs(title = "Memory Usage Over Time (GB)",
       x = "Time (hours)", y = "GB", fill = "Metric") +
  theme_minimal() +
  theme(legend.position = "bottom")

# --- 5c. GPU utilization per node (only if GPU columns exist) ---
has_gpu <- "gpu_usage_total" %in% colnames(all_data)
has_gpu_mem <- all(c("gpu_mem_0", "gpu_mem_1", "gpu_mem_2", "gpu_mem_3") %in% colnames(all_data))

if (has_gpu) {
  gpu_data <- all_data |>
    select(node, time_hours, gpu_usage_total)

  p3 <- ggplot(gpu_data, aes(x = time_hours, y = gpu_usage_total)) +
    geom_area(alpha = 0.7, fill = "steelblue") +
    facet_wrap(~ node, ncol = 1, scales = "free_y") +
    labs(title = "GPU Utilization Over Time",
         x = "Time (hours)", y = "GPU %") +
    theme_minimal()
}

if (has_gpu_mem) {
  gpu_mem_data <- all_data |>
    select(node, time_hours, gpu_mem_0, gpu_mem_1, gpu_mem_2, gpu_mem_3) |>
    mutate(gpu_mem_total_gb = rowSums(across(c(gpu_mem_0, gpu_mem_1, gpu_mem_2, gpu_mem_3)), na.rm = TRUE) / (1024^3))

  p4 <- ggplot(gpu_mem_data, aes(x = time_hours, y = gpu_mem_total_gb)) +
    geom_area(alpha = 0.7, fill = "steelblue") +
    facet_wrap(~ node, ncol = 1, scales = "free_y") +
    labs(title = "GPU Memory Usage Over Time (Total GB)",
         x = "Time (hours)", y = "GB") +
    theme_minimal()
}

# --- 5e. Summary violin plots across nodes ---
# CPU total usage by node (100% - idle%)
cpu_total_data <- cpu_data |>
  filter(metric == "idl") |>
  mutate(cpu_total = 100 - value)

p5 <- ggplot(cpu_total_data,
       aes(x = factor(node), y = cpu_total, fill = factor(node))) +
  geom_violin(alpha = 0.7) +
  scale_fill_brewer(palette = "Blues") +
  scale_y_continuous(limits = c(0, 100)) +
  labs(title = "CPU Total Usage % by Node",
       x = "Node", y = "CPU Usage %") +
  theme_minimal() +
  theme(legend.position = "none")

if (has_gpu) {
  p6 <- ggplot(gpu_data,
         aes(x = factor(node), y = gpu_usage_total, fill = factor(node))) +
    geom_violin(alpha = 0.7) +
    scale_fill_brewer(palette = "Greens") +
    scale_y_continuous(limits = c(0, 100)) +
    labs(title = "GPU Usage % by Node",
         x = "Node", y = "GPU %") +
    theme_minimal() +
    theme(legend.position = "none")
}

# --- Write PDF ---
# Open multi-page PDF device
pdf(output_pdf, width = 14, height = 10)

# Page 1: CPU usage on top, GPU utilization below (if available)
if (has_gpu) {
  print(p1 / p3 + plot_layout(ncol = 1, heights = c(1, 1)) & theme(axis.text.x = element_text(angle = 45, hjust = 1)))
} else {
  print(p1 + theme(axis.text.x = element_text(angle = 45, hjust = 1)))
}

# Page 2: Memory usage on top, GPU memory below (if available)
if (has_gpu_mem) {
  print(p2 / p4 + plot_layout(ncol = 1, heights = c(1, 1)) & theme(axis.text.x = element_text(angle = 45, hjust = 1)))
} else {
  print(p2 + theme(axis.text.x = element_text(angle = 45, hjust = 1)))
}

# Page 3: CPU total usage + GPU usage violin plots (if GPU available)
if (has_gpu) {
  print(p5 + p6 + plot_layout(nrow = 1, widths = c(1, 1)))
} else {
  print(p5)
}

# Close PDF device
dev.off()

# --- 6. Done ---
cat("\n--- Processing Complete ---\n")
cat("All plots saved to:", output_pdf, "\n")
