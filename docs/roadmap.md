# Project Roadmap

## Version 0.2 (Current)

### Core Infrastructure
- [x] Integrate TypeScript QM parser
- [x] Implement Python environment
- [x] Remove TextArena dependency
- [x] Implement basic agent interface
- [x] Add quest renderer

### In Progress
- [ ] Improve TypeScript Bridge stability
- [ ] Simplify environment interface
- [ ] Add more test coverage

### Known Issues
- TypeScript Bridge occasionally fails to parse complex quests
- Some tests failing after environment updates

### Next Steps
1. Improve bridge stability
2. Add more test coverage
3. Document new environment interface
4. Release version 0.2

## Future Versions

### Version 0.3 (High Priority)
- [ ] Separate rendering from quest workflow
  - Move renderer to visualization module
  - Create headless quest runner for simulations
  - Add support for parallel quest execution
  - Implement visualization tools for multiple quest runs
- [ ] Improve logging and debugging
  - Streamline debug output format
  - Add structured logging for quest states
  - Implement clean separation between game state and rendering
  - Add support for logging multiple parallel runs

### Version 0.4
- [ ] Enhance agent capabilities
  - Add support for strategic planning
  - Implement chain-of-thought prompting
  - Support for custom agent architectures
- [ ] Improve quest analysis tools
  - Add quest complexity metrics
  - Implement performance comparison tools
  - Support for automated agent evaluation

### Future Ideas
- Quest editor and validation tools
- Support for custom rewards
- Additional quest features